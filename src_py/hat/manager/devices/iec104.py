import functools
import itertools

from hat import aio
from hat import json
from hat import util
from hat.drivers import iec104
from hat.manager import common


default_master_conf = {'host': '127.0.0.1',
                       'port': 2404,
                       'response_timeout': 15,
                       'supervisory_timeout': 10,
                       'test_timeout': 20,
                       'send_window_size': 12,
                       'receive_window_size': 8}

default_slave_conf = {'properties': {'host': '127.0.0.1',
                                     'port': 2404,
                                     'response_timeout': 15,
                                     'supervisory_timeout': 10,
                                     'test_timeout': 20,
                                     'send_window_size': 12,
                                     'receive_window_size': 8},
                      'data': [],
                      'commands': []}


class Master(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._async_group = aio.Group()
        self._change_cbs = util.CallbackRegistry()
        self._conn = None
        self._data = {'properties': conf,
                      'data': []}

    @property
    def async_group(self):
        return self._async_group

    @property
    def data(self):
        return self._data

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    def get_conf(self):
        return self._data['properties']

    async def create(self):
        properties = self._data['properties']
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
                self._update_data(data)

        except ConnectionError:
            pass

        finally:
            conn.close()

    def _act_set_property(self, path, value):
        self._set(['properties', path], value)

    async def _act_interrogate(self, asdu):
        data = await self._conn.interrogate(asdu)
        self._update_data(data)

    async def _act_counter_interrogate(self, asdu, freeze):
        freeze = iec104.FreezeCode[freeze]
        data = await self._conn.counter_interrogate(asdu, freeze)
        self._update_data(data)

    async def _act_send_command(self, cmd):
        cmd = _cmd_from_json(cmd)
        result = await self._conn.send_command(cmd)
        return result

    def _update_data(self, new_data):
        if not new_data:
            return
        new_data = [_data_to_json(i) for i in new_data]
        new_data_ids = {(i['type'], i['asdu'], i['io']) for i in new_data}
        old_data = (i for i in self._data
                    if (i['type'], i['asdu'], i['io']) not in new_data_ids)
        data = sorted(itertools.chain(old_data, new_data),
                      key=lambda i: (i['type'], i['asdu'], i['io']))
        self._set('data', data)

    def _set(self, path, value):
        self._data = json.set_(self._data, path, value)
        self._change_cbs.notify(self._data)

    def _remove(self, path):
        self._data = json.remove(self._data, path)
        self._change_cbs.notify(self._data)


class Slave(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._async_group = aio.Group()
        self._change_cbs = util.CallbackRegistry()
        self._data_change_cbs = util.CallbackRegistry()
        self._next_ids = (str(i) for i in itertools.count(1))
        self._data = {
            'properties': conf['properties'],
            'connection_count': 0,
            'data': {next(self._next_ids): i for i in conf['data']},
            'commands': {next(self._next_ids): i for i in conf['commands']}}

    @property
    def async_group(self):
        return self._async_group

    @property
    def data(self):
        return self._data

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    def get_conf(self):
        return {'properties': self._data['properties'],
                'data': list(self._data['data'].values()),
                'commands': list(self._data['commands'].values())}

    async def create(self):
        properties = self._data['properties']
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
            return await self._act_add_data(*args)

        if action == 'remove_data':
            return await self._act_remove_data(*args)

        if action == 'change_data':
            return await self._act_change_data(*args)

        if action == 'add_command':
            return await self._act_add_command(*args)

        if action == 'remove_command':
            return await self._act_remove_command(*args)

        if action == 'change_command':
            return await self._act_change_command(*args)

        raise ValueError('invalid action')

    async def _connection_loop(self, conn):
        try:
            self._set('connection_count', self._data['connection_count'] + 1)
            change_cb = functools.partial(self._on_data_change, conn)
            with self._data_change_cbs.register(change_cb):
                while True:
                    await conn.receive()

        except ConnectionError:
            pass

        finally:
            conn.close()
            self._set('connection_count', self._data['connection_count'] - 1)

    def _on_interrogate(self, conn, asdu):
        data = [_data_from_json(i) for i in self._data['data'].values()
                if i['type'] != 'BinaryCounter' and (asdu == 0xFFFF or
                                                     asdu == i['asdu'])]
        return data

    def _on_counter_interrogate(self, conn, asdu, freeze):
        data = [_data_from_json(i) for i in self._data['data'].values()
                if i['type'] == 'BinaryCounter' and (asdu == 0xFFFF or
                                                     asdu == i['asdu'])]
        return data

    def _on_command(self, conn, cmd):
        key = _value_to_type(cmd.value), cmd.asdu_address, cmd.io_address
        command = util.first(self._data['commands'].values(),
                             lambda i: (i['type'], i['asdu'], i['io']) == key)
        success = bool(command['success']) if command else False
        return success

    def _on_data_change(self, conn, data):
        data = _data_from_json(data)
        conn.notify_data_change([data])

    def _act_set_property(self, path, value):
        self._set(['properties', path], value)

    def _act_add_data(self):
        data_id = next(self._next_ids)
        self._set(['data', data_id], {'type': None,
                                      'asdu': None,
                                      'io': None,
                                      'value': None,
                                      'quality': None,
                                      'time': None,
                                      'cause': None,
                                      'is_test': None})

    def _act_remove_data(self, data_id):
        self._remove(['data', data_id])

    def _act_change_data(self, data_id, path, value):
        self._set(['data', data_id, path], value)
        self._data_change_cbs.notify(self._data['data'][data_id])

    def _act_add_command(self):
        command_id = next(self._next_ids)
        self._set(['commands', command_id], {'type': None,
                                             'asdu': None,
                                             'io': None,
                                             'success': None})

    def _act_remove_command(self, command_id):
        self._remove(['commands', command_id])

    def _act_change_command(self, command_id, path, value):
        self._set(['commands', command_id, path], value)

    def _set(self, path, value):
        self._data = json.set_(self._data, path, value)
        self._change_cbs.notify(self._data)

    def _remove(self, path):
        self._data = json.remove(self._data, path)
        self._change_cbs.notify(self._data)


def _data_to_json(data):
    pass


def _data_from_json(data):
    pass


def _cmd_from_json(cmd):
    pass


def _value_to_type(value):
    if isinstance(value, iec104.SingleValue):
        return 'Single'

    if isinstance(value, iec104.DoubleValue):
        return 'Double'

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

    if isinstance(value, iec104.RegulatingValue):
        return 'Regulating'

    raise ValueError('invalid value')
