import itertools
import time

from hat.drivers import modbus
from hat.drivers import tcp
from hat.manager import common


default_master_conf = {'properties': {'link_type': 'TCP',
                                      'modbus_type': 'TCP',
                                      'tcp_host': '127.0.0.1',
                                      'tcp_port': 1502,
                                      'serial_port': '/dev/ttyS0',
                                      'serial_silent_interval': 0.005}}

default_slave_conf = {'properties': {'link_type': 'TCP',
                                     'modbus_type': 'TCP',
                                     'tcp_host': '127.0.0.1',
                                     'tcp_port': 1502,
                                     'serial_port': '/dev/ttyS0',
                                     'serial_silent_interval': 0.005},
                      'data': []}

master_data_size = 100


class Master(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._master = None
        self._data = common.DataStorage({'properties': conf['properties'],
                                         'data': []})

    @property
    def data(self):
        return self._data

    def get_conf(self):
        return {'properties': self._data.data['properties']}

    async def create(self):
        properties = self._data.data['properties']
        modbus_type = modbus.ModbusType[properties['modbus_type']]

        if properties['link_type'] == 'TCP':
            self._master = await modbus.create_tcp_master(
                modbus_type=modbus_type,
                addr=tcp.Address(properties['tcp_host'],
                                 properties['tcp_port']))
            return self._master

        if properties['link_type'] == 'SERIAL':
            self._master = await modbus.create_serial_master(
                modbus_type=modbus_type,
                port=properties['serial_port'],
                silent_interval=properties['serial_silent_interval'])
            return self._master

        raise ValueError('invalid link type')

    async def execute(self, action, *args):
        if action == 'set_property':
            return self._act_set_property(*args)

        if action == 'read':
            return await self._act_read(*args)

        if action == 'write':
            return await self._act_write(*args)

        raise ValueError('invalid action')

    def _act_set_property(self, path, value):
        self._logger.log(f'changing property {path} to {value}')
        self._data.set(['properties', path], value)

    async def _act_read(self, device_id, data_type, start_address, quantity):
        if not self._master or not self._master.is_open:
            self._logger.log('read failed - not connected')
            return

        result = await self._master.read(device_id=device_id,
                                         data_type=modbus.DataType[data_type],
                                         start_address=start_address,
                                         quantity=quantity)
        value = (result.name if isinstance(result, modbus.Error)
                 else ', '.join(str(i) for i in result))
        self._add_data('read', device_id, data_type, start_address, value)

    async def _act_write(self, device_id, data_type, start_address, values):
        if not self._master or not self._master.is_open:
            self._logger.log('write failed - not connected')
            return

        result = await self._master.write(device_id=device_id,
                                          data_type=modbus.DataType[data_type],
                                          start_address=start_address,
                                          values=values)
        value = result.name if result else ', '.join(str(i) for i in values)
        self._add_data('write', device_id, data_type, start_address, value)

    def _add_data(self, action, device_id, data_type, start_address, value):
        entry = {'timestamp': time.time(),
                 'action': action,
                 'device_id': device_id,
                 'data_type': data_type,
                 'start_address': start_address,
                 'value': value}
        data = itertools.chain([entry], self._data.data['data'])
        data = itertools.islice(data, master_data_size)
        self._data.set('data', list(data))


class Slave(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._next_data_ids = (str(i) for i in itertools.count(1))
        self._data = common.DataStorage({
            'properties': conf['properties'],
            'slave_count': 0,
            'data': {next(self._next_data_ids): i
                     for i in conf['data']}})

    @property
    def data(self):
        return self._data

    def get_conf(self):
        return {'properties': self._data.data['properties'],
                'data': list(self._data.data['data'].values())}

    async def create(self):
        properties = self._data.data['properties']
        modbus_type = modbus.ModbusType[properties['modbus_type']]

        if properties['link_type'] == 'TCP':
            srv = await modbus.create_tcp_server(
                modbus_type=modbus_type,
                addr=tcp.Address(properties['tcp_host'],
                                 properties['tcp_port']),
                slave_cb=self._slave_loop,
                read_cb=self._on_read,
                write_cb=self._on_write,
                write_mask_cb=self._on_write_mask)
            return srv

        if properties['link_type'] == 'SERIAL':
            slave = await modbus.create_serial_slave(
                modbus_type=modbus_type,
                port=properties['serial_port'],
                read_cb=self._on_read,
                write_cb=self._on_write,
                write_mask_cb=self._on_write_mask,
                silent_interval=properties['serial_silent_interval'])
            slave.async_group.spawn(self._slave_loop, slave)
            return slave

        raise ValueError('invalid link type')

    async def execute(self, action, *args):
        if action == 'set_property':
            return self._act_set_property(*args)

        if action == 'add_data':
            return self._act_add_data(*args)

        if action == 'remove_data':
            return self._act_remove_data(*args)

        if action == 'change_data':
            return self._act_change_data(*args)

        raise ValueError('invalid action')

    async def _slave_loop(self, slave):
        try:
            self._logger.log('new slave created')
            self._data.set('slave_count', self._data.data['slave_count'] + 1)
            await slave.wait_closing()

        except ConnectionError:
            pass

        finally:
            slave.close()
            self._logger.log('slave closed')
            self._data.set('slave_count', self._data.data['slave_count'] - 1)

    def _on_read(self, slave, device_id, data_type, start_address, quantity):
        self._logger.log('received read request')
        quantity = quantity or 1
        data = {i['address']: i['value']
                for i in self._data.data['data'].values()
                if device_id == i['device_id'] and
                data_type.name == i['data_type'] and
                i['address'] is not None and
                start_address <= i['address'] < start_address + quantity}
        result = [(data.get(i) or 0)
                  for i in range(start_address, start_address + quantity)]
        return result

    def _on_write(self, slave, device_id, data_type, start_address, values):
        self._logger.log('received write request')
        quantity = len(values)
        data = {}
        for data_id, i in self._data.data['data'].items():
            if ((device_id == i['device_id'] or device_id == 0) and
                    data_type.name == i['data_type'] and
                    i['address'] is not None and
                    start_address <= i['address'] < start_address + quantity):
                data[data_id] = values[i['address'] - start_address]

        self._logger.log(f'changing data values (count: {len(data)})')
        for data_id, value in data.items():
            self._data.set(['data', data_id, 'value'], value)

    def _on_write_mask(self, slave, device_id, address, and_mask, or_mask):
        self._logger.log('received write mask request')
        data = {}
        for data_id, i in self._data.data['data'].items():
            if ((device_id == i['device_id'] or device_id == 0) and
                    i['data_type'] == 'HOLDING_REGISTER' and
                    i['address'] == address):
                data[data_id] = modbus.apply_mask(value=i['value'] or 0,
                                                  and_mask=and_mask,
                                                  or_mask=or_mask)

        self._logger.log(f'changing data values (count: {len(data)})')
        for data_id, value in data.items():
            self._data.set(['data', data_id, 'value'], value)

    def _act_set_property(self, path, value):
        self._logger.log(f'changing property {path} to {value}')
        self._data.set(['properties', path], value)

    def _act_add_data(self):
        self._logger.log('creating new data')
        data_id = next(self._next_data_ids)
        self._data.set(['data', data_id], {'device_id': None,
                                           'data_type': None,
                                           'address': None,
                                           'value': None})
        return data_id

    def _act_remove_data(self, data_id):
        self._logger.log('removing data')
        self._data.remove(['data', data_id])

    def _act_change_data(self, data_id, path, value):
        self._logger.log(f'changing data {path} to {value}')
        self._data.set(['data', data_id, path], value)
