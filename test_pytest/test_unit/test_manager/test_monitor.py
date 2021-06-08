import pytest

from hat import aio
from hat import json
from hat import juggler
from hat import util
from hat.manager import common
import hat.manager.devices.monitor

pytestmark = pytest.mark.asyncio


@pytest.fixture
def port():
    return util.get_unused_tcp_port()


@pytest.fixture
def addr(port):
    return f'ws://127.0.0.1:{port}/ws'


@pytest.fixture
async def server(port):
    server = Server()
    server._data = common.DataStorage()
    server._receive_queue = aio.Queue()
    server._srv = await juggler.listen('127.0.0.1', port,
                                       server._on_connection,
                                       autoflush_delay=0)
    try:
        yield server
    finally:
        await server.async_close()


class Server(aio.Resource):

    @property
    def async_group(self):
        return self._srv.async_group

    @property
    def data(self):
        return self._data

    @property
    def receive_queue(self):
        return self._receive_queue

    def _on_connection(self, conn):
        self.async_group.spawn(self._connection_loop, conn)

    async def _connection_loop(self, conn):
        try:
            with self._data.register_change_cb(conn.set_local_data):
                conn.set_local_data(self._data.data)
                while True:
                    msg = await conn.receive()
                    self._receive_queue.put_nowait(msg)

        finally:
            conn.close()


def create_change_queue(data_storage, path):
    queue = aio.Queue()
    last_value = None

    def on_change(data):
        nonlocal last_value
        new_value = json.get(data, path)
        if new_value == last_value:
            return
        queue.put_nowait(new_value)
        last_value = new_value

    data_storage.register_change_cb(on_change)
    on_change(data_storage.data)
    return queue


async def test_create(addr, server):
    conf = {'address': addr}
    logger = common.Logger()
    device = hat.manager.devices.monitor.Device(conf, logger)
    client = await device.create()

    assert client.is_open

    await client.async_close()


async def test_set_address():
    conf = {'address': 'addr1'}
    logger = common.Logger()
    device = hat.manager.devices.monitor.Device(conf, logger)
    assert device.data.data['address'] == 'addr1'

    await device.execute('set_address', 'addr2')
    assert device.data.data['address'] == 'addr2'

    new_conf = device.get_conf()
    assert new_conf['address'] == 'addr2'


async def test_set_rank(addr, server):
    conf = {'address': addr}
    logger = common.Logger()
    device = hat.manager.devices.monitor.Device(conf, logger)
    client = await device.create()

    await device.execute('set_rank', 1234, 4321)

    msg = await server.receive_queue.get()

    assert msg == {'type': 'set_rank',
                   'payload': {'cid': 1234,
                               'rank': 4321}}

    await client.async_close()
