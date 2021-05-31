import pytest

from hat import aio
from hat import util
from hat.drivers import modbus
from hat.drivers import tcp
from hat.gateway import common
from hat.gateway.devices.modbus import master
import hat.event.common


pytestmark = pytest.mark.asyncio


gateway_name = 'gateway_name'
device_name = 'device_name'
event_type_prefix = ('gateway', gateway_name, master.device_type, device_name)


class EventClient(common.DeviceEventClient):

    def __init__(self, query_result=[]):
        self._query_result = query_result
        self._receive_queue = aio.Queue()
        self._register_queue = aio.Queue()
        self._async_group = aio.Group()
        self._async_group.spawn(aio.call_on_cancel, self._receive_queue.close)
        self._async_group.spawn(aio.call_on_cancel, self._register_queue.close)

    @property
    def async_group(self):
        return self._async_group

    @property
    def receive_queue(self):
        return self._receive_queue

    @property
    def register_queue(self):
        return self._register_queue

    async def receive(self):
        try:
            return await self._receive_queue.get()
        except aio.QueueClosedError:
            raise ConnectionError()

    def register(self, events):
        try:
            for event in events:
                self._register_queue.put_nowait(event)
        except aio.QueueClosedError:
            raise ConnectionError()

    async def register_with_response(self, events):
        raise Exception('should not be used')

    async def query(self, data):
        return self._query_result


def assert_status_event(event, status):
    assert event.event_type == (*event_type_prefix, 'gateway', 'status')
    assert event.payload.data == status


def assert_remote_device_status_event(event, device_id, status):
    assert event.event_type == (*event_type_prefix, 'gateway',
                                'remote_device', str(device_id), 'status')
    assert event.payload.data == status


def assert_remote_device_read_event(event, device_id, data_name,
                                    payload_data):
    assert event.event_type == (*event_type_prefix, 'gateway',
                                'remote_device', str(device_id), 'read',
                                data_name)
    assert event.payload.data == payload_data


def assert_remote_device_write_event(event, device_id, data_name,
                                     payload_data):
    assert event.event_type == (*event_type_prefix, 'gateway',
                                'remote_device', str(device_id), 'write',
                                data_name)
    assert event.payload.data == payload_data


@pytest.fixture
def slave_addr():
    return tcp.Address('127.0.0.1', util.get_unused_tcp_port())


@pytest.fixture
def connection_conf(slave_addr):
    return {'modbus_type': 'TCP',
            'transport': {'type': 'TCP',
                          'host': slave_addr.host,
                          'port': slave_addr.port},
            'connect_timeout': 5,
            'connect_delay': 5,
            'request_timeout': 2,
            'request_retry_count': 3,
            'request_retry_delay': 1}


@pytest.fixture
def create_event():
    counter = 0

    def create_event(event_type, payload_data):
        nonlocal counter
        counter += 1
        event_id = hat.event.common.EventId(1, counter)
        payload = hat.event.common.EventPayload(
            hat.event.common.EventPayloadType.JSON, payload_data)
        event = hat.event.common.Event(event_id=event_id,
                                       event_type=event_type,
                                       timestamp=hat.event.common.now(),
                                       source_timestamp=None,
                                       payload=payload)
        return event

    return create_event


@pytest.fixture
def create_remote_device_enable_event(create_event):

    def create_remote_device_enable_event(device_id, enable):
        return create_event((*event_type_prefix, 'system', 'remote_device',
                             str(device_id), 'enable'),
                            enable)

    return create_remote_device_enable_event


@pytest.fixture
def create_remote_device_write_event(create_event):

    def create_remote_device_write_event(device_id, data_name, request_id,
                                         value):
        return create_event((*event_type_prefix, 'system', 'remote_device',
                             str(device_id), 'write', data_name),
                            {'request_id': request_id,
                             'value': value})

    return create_remote_device_write_event


@pytest.mark.parametrize("conf", [
    {'connection': {'modbus_type': 'TCP',
                    'transport': {'type': 'TCP',
                                  'host': '127.0.0.1',
                                  'port': 1502},
                    'connect_timeout': 5,
                    'connect_delay': 5,
                    'request_timeout': 2,
                    'request_retry_count': 3,
                    'request_retry_delay': 1},
     'remote_devices': [{'device_id': 1,
                         'data': [{'name': 'data1',
                                   'interval': 5,
                                   'data_type': 'COIL',
                                   'start_address': 123,
                                   'bit_offset': 0,
                                   'bit_count': 3}]}]},

    {'connection': {'modbus_type': 'RTU',
                    'transport': {'type': 'SERIAL',
                                  'port': '/dev/ttyS0',
                                  'baudrate': 9600,
                                  'bytesize': 'EIGHTBITS',
                                  'parity': 'NONE',
                                  'stopbits': 'ONE',
                                  'flow_control': {'xonxoff': False,
                                                   'rtscts': False,
                                                   'dsrdtr': False},
                                  'silent_interval': 0.005},
                    'connect_timeout': 5,
                    'connect_delay': 5,
                    'request_timeout': 2,
                    'request_retry_count': 3,
                    'request_retry_delay': 1},
     'remote_devices': [{'device_id': 1,
                         'data': [{'name': 'data1',
                                   'interval': None,
                                   'data_type': 'HOLDING_REGISTER',
                                   'start_address': 321,
                                   'bit_offset': 2,
                                   'bit_count': 2}]}]},
])
def test_valid_conf(conf):
    master.json_schema_repo.validate(master.json_schema_id, conf)


async def test_create(slave_addr, connection_conf):
    slave_queue = aio.Queue()
    server = await modbus.create_tcp_server(modbus.ModbusType.TCP, slave_addr,
                                            slave_cb=slave_queue.put_nowait)

    assert server.is_open
    assert slave_queue.empty()

    conf = {'connection': connection_conf,
            'remote_devices': []}

    event_client = EventClient()
    device = await aio.call(master.create, conf, event_client,
                            event_type_prefix)

    assert device.is_open

    slave = await slave_queue.get()
    assert slave.is_open

    await device.async_close()
    await slave.wait_closing()
    await server.async_close()
    await event_client.async_close()


async def test_reconnect(slave_addr, connection_conf):
    slave_queue = aio.Queue()
    server = await modbus.create_tcp_server(modbus.ModbusType.TCP, slave_addr,
                                            slave_cb=slave_queue.put_nowait)

    conf = {'connection': connection_conf,
            'remote_devices': []}

    event_client = EventClient()
    device = await aio.call(master.create, conf, event_client,
                            event_type_prefix)

    slave = await slave_queue.get()
    assert slave.is_open

    assert slave_queue.empty()

    await slave.async_close()

    assert device.is_open

    slave = await slave_queue.get()
    assert slave.is_open

    assert slave_queue.empty()

    await device.async_close()
    await slave.wait_closing()
    await server.async_close()
    await event_client.async_close()


async def test_status(slave_addr, connection_conf):
    slave_queue = aio.Queue()
    server = await modbus.create_tcp_server(modbus.ModbusType.TCP, slave_addr,
                                            slave_cb=slave_queue.put_nowait)

    conf = {'connection': connection_conf,
            'remote_devices': []}

    event_client = EventClient()
    assert event_client.register_queue.empty()

    device = await aio.call(master.create, conf, event_client,
                            event_type_prefix)

    event = await event_client.register_queue.get()
    assert_status_event(event, 'CONNECTING')

    event = await event_client.register_queue.get()
    assert_status_event(event, 'CONNECTED')

    assert event_client.register_queue.empty()

    slave = await slave_queue.get()
    await slave.async_close()

    event = await event_client.register_queue.get()
    assert_status_event(event, 'DISCONNECTED')

    event = await event_client.register_queue.get()
    assert_status_event(event, 'CONNECTING')

    event = await event_client.register_queue.get()
    assert_status_event(event, 'CONNECTED')

    assert event_client.register_queue.empty()

    await device.async_close()
    await slave.wait_closing()

    event = await event_client.register_queue.get()
    assert_status_event(event, 'DISCONNECTED')

    assert event_client.register_queue.empty()

    await server.async_close()
    await event_client.async_close()


async def test_remote_device_status(slave_addr, connection_conf,
                                    create_remote_device_enable_event):
    slave_queue = aio.Queue()
    server = await modbus.create_tcp_server(modbus.ModbusType.TCP, slave_addr,
                                            slave_cb=slave_queue.put_nowait)

    conf = {'connection': connection_conf,
            'remote_devices': [{'device_id': 1,
                                'data': []}]}

    event_client = EventClient()
    assert event_client.register_queue.empty()

    device = await aio.call(master.create, conf, event_client,
                            event_type_prefix)

    event = await event_client.register_queue.get()
    assert_status_event(event, 'CONNECTING')

    event = await event_client.register_queue.get()
    assert_status_event(event, 'CONNECTED')

    event = await event_client.register_queue.get()
    assert_remote_device_status_event(event, 1, 'DISABLED')

    assert event_client.register_queue.empty()

    slave = await slave_queue.get()

    event = create_remote_device_enable_event(1, True)
    event_client.receive_queue.put_nowait([event])

    event = await event_client.register_queue.get()
    assert_remote_device_status_event(event, 1, 'CONNECTED')

    event = create_remote_device_enable_event(1, False)
    event_client.receive_queue.put_nowait([event])

    event = await event_client.register_queue.get()
    assert_remote_device_status_event(event, 1, 'DISABLED')

    event = create_remote_device_enable_event(1, True)
    event_client.receive_queue.put_nowait([event])

    event = await event_client.register_queue.get()
    assert_remote_device_status_event(event, 1, 'CONNECTED')

    await device.async_close()
    await slave.wait_closing()

    event = await event_client.register_queue.get()
    assert_remote_device_status_event(event, 1, 'DISABLED')

    event = await event_client.register_queue.get()
    assert_status_event(event, 'DISCONNECTED')

    assert event_client.register_queue.empty()

    await server.async_close()
    await event_client.async_close()


@pytest.mark.parametrize('data_type, bit_offset, bit_count, registers, value', [  # NOQA
    ('COIL',
     0,
     1,
     [0],
     0),

    ('COIL',
     0,
     1,
     [1],
     1),

    ('DISCRETE_INPUT',
     0,
     2,
     [1, 1],
     3),

    ('HOLDING_REGISTER',
     0,
     32,
     [0, 1],
     1),

    ('HOLDING_REGISTER',
     0,
     2,
     [0x4000],
     1),

    ('INPUT_REGISTER',
     8,
     2,
     [0x80],
     2),
])
async def test_read(slave_addr, connection_conf,
                    create_remote_device_enable_event,
                    data_type, bit_offset, bit_count, registers, value):

    async def on_read(slave, device_id, _data_type, start_address, quantity):
        assert device_id == 1
        assert data_type == _data_type.name
        assert start_address == 123
        assert quantity == len(registers)
        return registers

    server = await modbus.create_tcp_server(modbus.ModbusType.TCP, slave_addr,
                                            read_cb=on_read)

    conf = {'connection': connection_conf,
            'remote_devices': [{'device_id': 1,
                                'data': [{'name': 'data',
                                          'interval': 1,
                                          'data_type': data_type,
                                          'start_address': 123,
                                          'bit_offset': bit_offset,
                                          'bit_count': bit_count}]}]}

    event_client = EventClient([create_remote_device_enable_event(1, True)])
    device = await aio.call(master.create, conf, event_client,
                            event_type_prefix)

    event = await event_client.register_queue.get()
    assert_status_event(event, 'CONNECTING')

    event = await event_client.register_queue.get()
    assert_status_event(event, 'CONNECTED')

    event = await event_client.register_queue.get()
    assert_remote_device_status_event(event, 1, 'CONNECTING')

    event = await event_client.register_queue.get()
    assert_remote_device_read_event(event, 1, 'data', {'result': 'SUCCESS',
                                                       'value': value,
                                                       'cause': 'INTERROGATE'})

    event = await event_client.register_queue.get()
    assert_remote_device_status_event(event, 1, 'CONNECTED')

    await device.async_close()

    event = await event_client.register_queue.get()
    assert_remote_device_status_event(event, 1, 'DISABLED')

    event = await event_client.register_queue.get()
    assert_status_event(event, 'DISCONNECTED')

    assert event_client.register_queue.empty()

    await server.async_close()
    await event_client.async_close()


@pytest.mark.parametrize('data_type, bit_offset, bit_count, registers, value', [  # NOQA
    ('COIL',
     0,
     1,
     [0],
     0),

    ('COIL',
     0,
     1,
     [1],
     1),

    ('COIL',
     2,
     2,
     [0, 0, 1, 1],
     3),

    ('HOLDING_REGISTER',
     0,
     16,
     [123],
     123),

    ('HOLDING_REGISTER',
     0,
     32,
     [0x1234, 0x5678],
     0x12345678),

    ('HOLDING_REGISTER',
     0,
     2,
     [0xc000],
     3),

    ('HOLDING_REGISTER',
     2,
     2,
     [0x3000],
     3),

    ('HOLDING_REGISTER',
     8,
     16,
     [0xFF, 0xFF00],
     0xFFFF),

    ('HOLDING_REGISTER',
     8,
     32,
     [0xFF, 0xFFFF, 0xFF00],
     0xFFFFFFFF),
])
async def test_write(slave_addr, connection_conf,
                     create_remote_device_write_event,
                     data_type, bit_offset, bit_count, registers, value):

    data = [0] * len(registers)

    async def on_write_mask(slave, device_id, address, and_mask, or_mask):
        assert device_id == 1
        data[address] = modbus.apply_mask(data[address], and_mask, or_mask)

    async def on_write(slave, device_id, _data_type, start_address, registers):
        assert device_id == 1
        assert data_type == _data_type.name
        for i, register in enumerate(registers):
            data[start_address + i] = register

    server = await modbus.create_tcp_server(modbus.ModbusType.TCP, slave_addr,
                                            write_cb=on_write,
                                            write_mask_cb=on_write_mask)

    conf = {'connection': connection_conf,
            'remote_devices': [{'device_id': 1,
                                'data': [{'name': 'data',
                                          'interval': None,
                                          'data_type': data_type,
                                          'start_address': 0,
                                          'bit_offset': bit_offset,
                                          'bit_count': bit_count}]}]}

    event_client = EventClient()
    device = await aio.call(master.create, conf, event_client,
                            event_type_prefix)

    event = await event_client.register_queue.get()
    assert_status_event(event, 'CONNECTING')

    event = await event_client.register_queue.get()
    assert_status_event(event, 'CONNECTED')

    event = await event_client.register_queue.get()
    assert_remote_device_status_event(event, 1, 'DISABLED')

    event = create_remote_device_write_event(1, 'data', 123, value)
    event_client.receive_queue.put_nowait([event])

    event = await event_client.register_queue.get()
    assert_remote_device_write_event(event, 1, 'data', {'request_id': 123,
                                                        'result': 'SUCCESS'})

    await device.async_close()

    event = await event_client.register_queue.get()
    assert_status_event(event, 'DISCONNECTED')

    assert event_client.register_queue.empty()

    await server.async_close()
    await event_client.async_close()

    assert data == registers
