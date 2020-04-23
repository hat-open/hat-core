import pytest

import hat.monitor.server.ui
from hat.monitor.common import ComponentInfo
from hat import util
from hat.util import aio
from hat import juggler


async def create_client(address):
    client = Client()
    client._conn = await juggler.connect(address)
    return client


class Client:

    @property
    def closed(self):
        return self._conn.closed

    async def async_close(self):
        await self._conn.async_close()

    @property
    def mid(self):
        return self._conn.remote_data['mid']

    @property
    def components(self):
        return [ComponentInfo(
            cid=i['cid'],
            mid=i['mid'],
            name=i['name'],
            group=i['group'],
            address=i['address'],
            rank=i['rank'],
            blessing=i['blessing'],
            ready=i['ready']) for i in self._conn.remote_data['components']]

    def register_change_cb(self, cb):
        return self._conn.register_change_cb(cb)

    async def set_rank(self, cid, mid, rank):
        payload = {'cid': cid,
                   'mid': mid,
                   'rank': rank}
        await self._conn.send({'type': 'set_rank',
                               'payload': payload})


class MockServer():

    def __init__(self, mid=0):
        self._async_group = aio.Group()
        self._mid = mid
        self._components = []
        self._rank_queue = aio.Queue()
        self._change_cbs = util.CallbackRegistry()

    @property
    def closed(self):
        return self._async_group.closed

    @property
    def components(self):
        return self._components

    @property
    def mid(self):
        return self._mid

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    async def async_close(self):
        await self._async_group.async_close()

    def set_master(self, master):
        raise NotImplementedError()

    def set_rank(self, cid, mid, rank):
        self._rank_queue.put_nowait((cid, mid, rank))

    def _set_mid(self, mid):
        self._mid = mid
        self._change_cbs.notify()

    def _set_components(self, components):
        self._components = components
        self._change_cbs.notify()


@pytest.fixture
def server_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def ui_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.mark.asyncio
async def test_backend_to_frontend(server_port, ui_port, tmpdir):
    c1 = ComponentInfo(cid=1, mid=10, name='c1', group='g1', address=None,
                       rank=1, blessing=None, ready=None)
    c2 = ComponentInfo(cid=2, mid=11, name='c2', group='g2', address='1.2.3.4',
                       rank=2, blessing=3, ready=3)

    ui_address = f'ws://127.0.0.1:{ui_port}/ws'
    ui_conf = {'address': ui_address}
    monitor_server = MockServer(mid=0)
    ui_backend = await hat.monitor.server.ui.create(ui_conf, tmpdir,
                                                    monitor_server)
    client = await create_client(ui_address)

    client_change_queue = aio.Queue()
    client.register_change_cb(lambda: client_change_queue.put_nowait(None))

    await client_change_queue.get()
    assert client.mid == 0 and client.components == []

    monitor_server._set_mid(1)
    await client_change_queue.get()
    assert client.mid == 1 and client.components == []

    monitor_server._set_components([c1, c2])
    await client_change_queue.get()
    assert client.mid == 1 and client.components == [c1, c2]

    monitor_server._set_mid(2)
    await client_change_queue.get()
    assert client.mid == 2 and client.components == [c1, c2]

    monitor_server._set_components([c2])
    await client_change_queue.get()
    assert client.mid == 2 and client.components == [c2]

    monitor_server._set_components([c1])
    await client_change_queue.get()
    assert client.mid == 2 and client.components == [c1]

    monitor_server._set_components([])
    await client_change_queue.get()
    assert client.mid == 2 and client.components == []

    await client.async_close()
    assert not ui_backend.closed.done()
    await monitor_server.async_close()
    await ui_backend.async_close()
    assert ui_backend.closed.done()


@pytest.mark.asyncio
async def test_frontend_to_backend(server_port, ui_port, tmpdir):
    ui_address = f'ws://localhost:{ui_port}/ws'
    ui_conf = {'address': ui_address}
    monitor_server = MockServer(mid=0)
    ui_backend = await hat.monitor.server.ui.create(ui_conf, tmpdir,
                                                    monitor_server)
    client = await create_client(ui_address)

    await client.set_rank(1, 2, 3)
    assert await monitor_server._rank_queue.get() == (1, 2, 3)

    await client.set_rank(-1, -2, -3)
    assert await monitor_server._rank_queue.get() == (-1, -2, -3)

    await client.async_close()
    assert not ui_backend.closed.done()
    await monitor_server.async_close()
    await ui_backend.async_close()
    assert ui_backend.closed.done()
