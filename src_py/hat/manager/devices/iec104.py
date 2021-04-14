import functools
import itertools
import time

from hat import util
from hat.drivers import iec104
from hat.manager import common


default_master_conf = {'properties': {'host': '127.0.0.1',
                                      'port': 2404,
                                      'response_timeout': 15,
                                      'supervisory_timeout': 10,
                                      'test_timeout': 20,
                                      'send_window_size': 12,
                                      'receive_window_size': 8}}

default_slave_conf = {'properties': {'host': '127.0.0.1',
                                     'port': 2404,
                                     'response_timeout': 15,
                                     'supervisory_timeout': 10,
                                     'test_timeout': 20,
                                     'send_window_size': 12,
                                     'receive_window_size': 8},
                      'data': [],
                      'commands': []}

master_data_size = 100


class Master(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._conn = None
        self._data = common.DataStorage({'properties': conf['properties'],
                                         'data': []})

    @property
    def data(self):
        return self._data

    def get_conf(self):
        return {'properties': self._data.data['properties']}

    async def create(self):
        properties = self._data.data['properties']
        self._conn = await iec104.connect(
            addr=iec104.Address(properties['host'],
                                properties['port']),
            response_timeout=properties['response_timeout'],
            supervisory_timeout=properties['supervisory_timeout'],
            test_timeout=properties['test_timeout'],
            send_window_size=properties['send_window_size'],
            receive_window_size=properties['receive_window_size'])
        self._conn.async_group.spawn(self._connection_loop, self._conn)
        return self._conn

    async def execute(self, action, *args):
        if action == 'set_property':
            return self._act_set_property(*args)

        if action == 'interrogate':
            return await self._act_interrogate(*args)

        if action == 'counter_interrogate':
            return await self._act_counter_interrogate(*args)

        if action == 'send_command':
            return await self._act_send_command(*args)

        raise ValueError('invalid action')

    async def _connection_loop(self, conn):
        try:
            while True:
                data = await conn.receive()
                self._logger.log(f'received data changes (cound: {len(data)})')
                self._add_data(data)

        except ConnectionError:
            pass

        finally:
            conn.close()

    def _act_set_property(self, path, value):
        self._logger.log(f'changing property {path} to {value}')
        self._data.set(['properties', path], value)

    async def _act_interrogate(self, asdu):
        if not self._conn or not self._conn.is_open:
            self._logger.log('interrogate failed - not connected')
            return

        self._logger.log(f'sending interrogate (asdu: {asdu})')
        data = await self._conn.interrogate(asdu)
        self._logger.log(f'received interrogate result (count: {len(data)})')
        self._add_data(data)

    async def _act_counter_interrogate(self, asdu, freeze):
        if not self._conn or not self._conn.is_open:
            self._logger.log('counter interrogate failed - not connected')
            return

        self._logger.log(f'sending counter interrogate (asdu: {asdu})')
        freeze = iec104.FreezeCode[freeze]
        data = await self._conn.counter_interrogate(asdu, freeze)
        self._logger.log(f'received counter interrogate result '
                         f'(count: {len(data)})')
        self._add_data(data)

    async def _act_send_command(self, cmd):
        if not self._conn or not self._conn.is_open:
            self._logger.log('command failed - not connected')
            return

        self._logger.log('sending command')
        cmd = _cmd_from_json(cmd)
        result = await self._conn.send_command(cmd)
        self._logger.log(f'received command result (success: {result})')
        return result

    def _add_data(self, data):
        if not data:
            return
        now = time.time()
        data = itertools.chain((dict(_data_to_json(i), timestamp=now)
                                for i in reversed(data)),
                               self._data.data['data'])
        data = itertools.islice(data, master_data_size)
        self._data.set('data', list(data))


class Slave(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._next_data_ids = (str(i) for i in itertools.count(1))
        self._next_command_ids = (str(i) for i in itertools.count(1))
        self._data_change_cbs = util.CallbackRegistry()
        self._data = common.DataStorage({
            'properties': conf['properties'],
            'connection_count': 0,
            'data': {next(self._next_data_ids): i
                     for i in conf['data']},
            'commands': {next(self._next_command_ids): dict(i, value=None)
                         for i in conf['commands']}})

    @property
    def data(self):
        return self._data

    def get_conf(self):
        return {'properties': self._data.data['properties'],
                'data': list(self._data.data['data'].values()),
                'commands': [{'type': i['type'],
                              'asdu': i['asdu'],
                              'io': i['io'],
                              'success': i['success']}
                             for i in self._data.data['commands'].values()]}

    async def create(self):
        properties = self._data.data['properties']
        srv = await iec104.listen(
            connection_cb=self._connection_loop,
            addr=iec104.Address(properties['host'],
                                properties['port']),
            interrogate_cb=self._on_interrogate,
            counter_interrogate_cb=self._on_counter_interrogate,
            command_cb=self._on_command,
            response_timeout=properties['response_timeout'],
            supervisory_timeout=properties['supervisory_timeout'],
            test_timeout=properties['test_timeout'],
            send_window_size=properties['send_window_size'],
            receive_window_size=properties['receive_window_size'])
        return srv

    async def execute(self, action, *args):
        if action == 'set_property':
            return self._act_set_property(*args)

        if action == 'add_data':
            return self._act_add_data(*args)

        if action == 'remove_data':
            return self._act_remove_data(*args)

        if action == 'change_data':
            return self._act_change_data(*args)

        if action == 'add_command':
            return self._act_add_command(*args)

        if action == 'remove_command':
            return self._act_remove_command(*args)

        if action == 'change_command':
            return self._act_change_command(*args)

        raise ValueError('invalid action')

    async def _connection_loop(self, conn):
        try:
            self._logger.log('new connection accepted')
            self._data.set('connection_count',
                           self._data.data['connection_count'] + 1)
            change_cb = functools.partial(self._on_data_change, conn)
            with self._data_change_cbs.register(change_cb):
                while True:
                    await conn.receive()

        except ConnectionError:
            pass

        finally:
            conn.close()
            self._logger.log('connection closed')
            self._data.set('connection_count',
                           self._data.data['connection_count'] - 1)

    def _on_interrogate(self, conn, asdu):
        self._logger.log(f'received interrogate request (asdu: {asdu})')
        data = (_data_from_json(i)
                for i in self._data.data['data'].values()
                if i['type'] != 'BinaryCounter' and (asdu == 0xFFFF or
                                                     asdu == i['asdu']))
        data = [i._replace(cause=iec104.Cause.INTERROGATED_STATION)
                for i in data if i]
        return data

    def _on_counter_interrogate(self, conn, asdu, freeze):
        self._logger.log(f'received counter interrogate request '
                         f'(asdu: {asdu})')
        data = (_data_from_json(i)
                for i in self._data.data['data'].values()
                if i['type'] == 'BinaryCounter' and (asdu == 0xFFFF or
                                                     asdu == i['asdu']))
        data = [i._replace(cause=iec104.Cause.INTERROGATED_COUNTER)
                for i in data if i]
        return data

    def _on_command(self, conn, cmd):
        self._logger.log(f'received command {cmd}')
        key = _value_to_type(cmd.value), cmd.asdu_address, cmd.io_address
        command_id, command = util.first(
            self._data['commands'].items(),
            lambda i: (i[1]['type'], i[1]['asdu'], i[1]['io']) == key,
            (None, None))
        success = bool(command['success']) if command else False
        if success:
            self._data.set(['commands', command_id, 'value'],
                           _value_to_json(cmd.value))
        self._logger.log(f'sending command success {success}')
        return success

    def _on_data_change(self, conn, data):
        data = _data_from_json(data)
        if not data:
            return
        conn.notify_data_change([data])

    def _act_set_property(self, path, value):
        self._logger.log(f'changing property {path} to {value}')
        self._data.set(['properties', path], value)

    def _act_add_data(self):
        self._logger.log('creating new data')
        data_id = next(self._next_data_ids)
        self._data.set(['data', data_id], {'type': None,
                                           'asdu': None,
                                           'io': None,
                                           'value': None,
                                           'quality': None,
                                           'time': None,
                                           'cause': None,
                                           'is_test': None})
        return data_id

    def _act_remove_data(self, data_id):
        self._logger.log('removing data')
        self._data.remove(['data', data_id])

    def _act_change_data(self, data_id, path, value):
        self._logger.log(f'changing data {path} to {value}')
        self._data.set(['data', data_id, path], value)
        self._data_change_cbs.notify(self._data.data['data'][data_id])

    def _act_add_command(self):
        self._logger.log('creating new command')
        command_id = next(self._next_command_ids)
        self._data.set(['commands', command_id], {'type': None,
                                                  'asdu': None,
                                                  'io': None,
                                                  'value': None,
                                                  'success': None})
        return command_id

    def _act_remove_command(self, command_id):
        self._logger.log('removing command')
        self._data.remove(['commands', command_id])

    def _act_change_command(self, command_id, path, value):
        self._logger.log(f'changing command {path} to {value}')
        self._data.set(['commands', command_id, path], value)


def _data_to_json(data):
    return {'type': _value_to_type(data.value),
            'asdu': data.asdu_address,
            'io': data.io_address,
            'value': _value_to_json(data.value),
            'quality': _quality_to_json(data.quality),
            'time': _time_to_json(data.time),
            'cause': _cause_to_json(data.cause),
            'is_test': data.is_test}


def _data_from_json(data):
    if not data['type'] or data['asdu'] is None or data['io'] is None:
        return
    return iec104.Data(
        value=_value_from_json(data['type'], data['value']),
        quality=_quality_from_json(data['type'], data['quality']),
        time=_time_from_json(data['time']),
        asdu_address=data['asdu'],
        io_address=data['io'],
        cause=_cause_from_json(data['cause']),
        is_test=data['is_test'] or False)


def _cmd_from_json(cmd):
    return iec104.Command(
        action=_action_from_json(cmd['action']),
        value=_value_from_json(cmd['type'], cmd['value']),
        asdu_address=cmd['asdu'],
        io_address=cmd['io'],
        time=_time_from_json(cmd['time']),
        qualifier=cmd['qualifier'] or 0)


def _value_to_json(value):
    if isinstance(value, iec104.SingleValue):
        return value.name

    if isinstance(value, iec104.DoubleValue):
        return value.name

    if isinstance(value, iec104.RegulatingValue):
        return value.name

    if isinstance(value, iec104.StepPositionValue):
        return value._asdict()

    if isinstance(value, iec104.BitstringValue):
        return value.value.hex()

    if isinstance(value, iec104.NormalizedValue):
        return value.value

    if isinstance(value, iec104.ScaledValue):
        return value.value

    if isinstance(value, iec104.FloatingValue):
        return value.value

    if isinstance(value, iec104.BinaryCounterValue):
        return value._asdict()

    raise ValueError('unsupported value')


def _value_from_json(data_type, value):
    if data_type == 'Single':
        try:
            return iec104.SingleValue[value]
        except Exception:
            return iec104.SingleValue.OFF

    if data_type == 'Double':
        try:
            return iec104.DoubleValue[value]
        except Exception:
            return iec104.DoubleValue.FAULT

    if data_type == 'Regulating':
        try:
            return iec104.RegulatingValue[value]
        except Exception:
            return iec104.RegulatingValue.LOWER

    if data_type == 'StepPosition':
        try:
            return iec104.StepPositionValue(value=int(value['value']),
                                            transient=bool(value['transient']))
        except Exception:
            return iec104.StepPositionValue(0, False)

    if data_type == 'Bitstring':
        try:
            return iec104.BitstringValue(
                (bytes.fromhex(value) + b'\x00\x00\x00\x00')[:4])
        except Exception:
            return iec104.BitstringValue(b'\x00\x00\x00\x00')

    if data_type == 'Normalized':
        try:
            return iec104.NormalizedValue(float(value))
        except Exception:
            return iec104.NormalizedValue(0)

    if data_type == 'Scaled':
        try:
            return iec104.ScaledValue(int(value))
        except Exception:
            return iec104.ScaledValue(0)

    if data_type == 'Floating':
        try:
            return iec104.FloatingValue(float(value))
        except Exception:
            return iec104.FloatingValue(0)

    if data_type == 'BinaryCounter':
        try:
            return iec104.BinaryCounterValue(value=int(value['value']),
                                             sequence=int(value['sequence']),
                                             overflow=bool(value['overflow']),
                                             adjusted=bool(value['adjusted']),
                                             invalid=bool(value['invalid']))
        except Exception:
            return iec104.BinaryCounterValue(0, 0, False, False, False)

    raise ValueError('unsupported data type')


def _quality_to_json(quality):
    if not quality:
        return
    return quality._asdict()


def _quality_from_json(data_type, quality):
    if data_type == 'BinaryCounter':
        return None
    quality = quality or {}
    if data_type in ('Single', 'Double'):
        overflow = None
    else:
        overflow = bool(quality.get('overflow'))
    return iec104.Quality(invalid=bool(quality.get('invalid')),
                          not_topical=bool(quality.get('not_topical')),
                          substituted=bool(quality.get('substituted')),
                          blocked=bool(quality.get('blocked')),
                          overflow=overflow)


def _time_to_json(time):
    return time._asdict() if time else None


def _time_from_json(time):
    if not time:
        return
    return iec104.Time(milliseconds=int(time['milliseconds']),
                       invalid=bool(time['invalid']),
                       minutes=int(time['minutes']),
                       summer_time=bool(time['summer_time']),
                       hours=int(time['hours']),
                       day_of_week=int(time['day_of_week']),
                       day_of_month=int(time['day_of_month']),
                       months=int(time['months']),
                       years=int(time['years']))


def _cause_to_json(cause):
    return cause.name


def _cause_from_json(cause):
    if not cause:
        return iec104.Cause.UNDEFINED
    return iec104.Cause[cause]


def _action_from_json(action):
    if not action:
        return iec104.Action.EXECUTE
    return iec104.Action[action]


def _value_to_type(value):
    if isinstance(value, iec104.SingleValue):
        return 'Single'

    if isinstance(value, iec104.DoubleValue):
        return 'Double'

    if isinstance(value, iec104.RegulatingValue):
        return 'Regulating'

    if isinstance(value, iec104.StepPositionValue):
        return 'StepPosition'

    if isinstance(value, iec104.BitstringValue):
        return 'Bitstring'

    if isinstance(value, iec104.NormalizedValue):
        return 'Normalized'

    if isinstance(value, iec104.ScaledValue):
        return 'Scaled'

    if isinstance(value, iec104.FloatingValue):
        return 'Floating'

    if isinstance(value, iec104.BinaryCounterValue):
        return 'BinaryCounter'

    raise ValueError('invalid value')
