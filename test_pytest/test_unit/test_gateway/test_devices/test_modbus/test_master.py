
import pytest

from hat import aio
from hat import util
from hat.drivers import modbus
from hat.drivers import tcp
from hat.gateway import common
from hat.gateway.devices.modbus import master


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
                                   'start_bit': 0,
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
                                   'start_bit': 2,
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
