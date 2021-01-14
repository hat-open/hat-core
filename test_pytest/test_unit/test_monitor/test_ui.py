
import pytest

from hat import util
from hat import juggler
from hat import aio
from hat.monitor.server import common
import hat.monitor.server.ui


pytestmark = pytest.mark.asyncio


@pytest.fixture
def ui_port():
    return util.get_unused_tcp_port()


@pytest.fixture
def ui_address(ui_port):
    return f'http://127.0.0.1:{ui_port}'


@pytest.fixture
def ui_juggler_address(ui_address):
    return f'{ui_address}/ws'


@pytest.fixture
def patch_autoflush_delay(monkeypatch):
    monkeypatch.setattr(hat.monitor.server.ui, 'autoflush_delay', 0)


async def connect(address):
    conn = await juggler.connect(address, autoflush_delay=0)
    conn.change_queue = aio.Queue()
    conn.register_change_cb(
        lambda: conn.change_queue.put_nowait(conn.remote_data))
    return conn


class Server(aio.Resource):

    def __init__(self):
        self._async_group = aio.Group()
        self._rank_queue = aio.Queue()
        self._local_components = []
        self._global_components = []
        self._change_cbs = util.CallbackRegistry()

    @property
    def rank_queue(self):
        return self._rank_queue

    @property
    def async_group(self):
        return self._async_group

    @property
    def mid(self):
        return 123

    @property
    def local_components(self):
        return self._local_components

    @property
    def global_components(self):
        return self._global_components

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    def update(self, mid, global_components):
        assert False

    def set_rank(self, cid, rank):
        self._rank_queue.put_nowait((cid, rank))

    def set_local_components(self, local_components):
        self._local_components = local_components
        self._change_cbs.notify()

    def set_global_components(self, global_components):
        self._global_components = global_components
        self._change_cbs.notify()


async def test_connect(tmp_path, patch_autoflush_delay, ui_address,
                       ui_juggler_address):
    conf = {'address': ui_address}

    server = Server()
    ui = await hat.monitor.server.ui.create(conf, tmp_path, server)

    conn = await connect(ui_juggler_address)

    assert ui.is_open
    assert conn.is_open

    state = await conn.change_queue.get()
    assert state == {'mid': server.mid,
                     'local_components': [],
                     'global_components': []}

    await ui.async_close()
    await conn.wait_closed()


@pytest.mark.parametrize("conn_count", [1, 2, 5])
async def test_local_components(tmp_path, patch_autoflush_delay, ui_address,
                                ui_juggler_address, conn_count):
    conf = {'address': ui_address}

    info = common.ComponentInfo(cid=1,
                                mid=2,
                                name='name',
                                group='group',
                                address='address',
                                rank=3,
                                blessing=4,
                                ready=5)

    server = Server()
    ui = await hat.monitor.server.ui.create(conf, tmp_path, server)

    conns = []
    for _ in range(conn_count):
        conn = await connect(ui_juggler_address)
        conns.append(conn)

        state = await conn.change_queue.get()
        assert state['local_components'] == []

    server.set_local_components([info])

    for conn in conns:
        state = await conn.change_queue.get()
        assert state['local_components'] == [{'cid': info.cid,
                                              'name': info.name,
                                              'group': info.group,
                                              'address': info.address,
                                              'rank': info.rank}]

    server.set_local_components([])

    for conn in conns:
        state = await conn.change_queue.get()
        assert state['local_components'] == []

    while conns:
        conn, conns = conns[0], conns[1:]
        await conn.async_close()

    await ui.async_close()


@pytest.mark.parametrize("conn_count", [1, 2, 5])
async def test_global_components(tmp_path, patch_autoflush_delay, ui_address,
                                 ui_juggler_address, conn_count):
    conf = {'address': ui_address}

    info = common.ComponentInfo(cid=1,
                                mid=2,
                                name='name',
                                group='group',
                                address='address',
                                rank=3,
                                blessing=4,
                                ready=5)

    server = Server()
    ui = await hat.monitor.server.ui.create(conf, tmp_path, server)

    conns = []
    for _ in range(conn_count):
        conn = await connect(ui_juggler_address)
        conns.append(conn)

        state = await conn.change_queue.get()
        assert state['global_components'] == []

    server.set_global_components([info])

    for conn in conns:
        state = await conn.change_queue.get()
        assert state['global_components'] == [{'cid': info.cid,
                                               'mid': info.mid,
                                               'name': info.name,
                                               'group': info.group,
                                               'address': info.address,
                                               'rank': info.rank,
                                               'blessing': info.blessing,
                                               'ready': info.ready}]

    server.set_global_components([])

    for conn in conns:
        state = await conn.change_queue.get()
        assert state['global_components'] == []

    while conns:
        conn, conns = conns[0], conns[1:]
        await conn.async_close()

    await ui.async_close()


async def test_set_rank(tmp_path, patch_autoflush_delay, ui_address,
                        ui_juggler_address):
    conf = {'address': ui_address}

    server = Server()
    ui = await hat.monitor.server.ui.create(conf, tmp_path, server)

    conn = await connect(ui_juggler_address)

    assert server.rank_queue.empty()

    await conn.send({'type': 'set_rank',
                     'payload': {'cid': 123,
                                 'rank': 321}})

    cid, rank = await server.rank_queue.get()
    assert cid == 123
    assert rank == 321

    await conn.async_close()
    await ui.async_close()
