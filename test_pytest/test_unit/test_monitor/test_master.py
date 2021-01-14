import pytest

from hat import aio
from hat import util
from hat import chatter
from hat.monitor.server import common
import hat.monitor.server.master


pytestmark = pytest.mark.asyncio


@pytest.fixture
def master_port():
    return util.get_unused_tcp_port()


@pytest.fixture
def master_address(master_port):
    return f'tcp+sbs://127.0.0.1:{master_port}'


async def connect(address):
    conn = Connection()
    conn._conn = await chatter.connect(common.sbs_repo, address)
    return conn


class Connection(aio.Resource):

    @property
    def async_group(self):
        return self._conn.async_group

    def send(self, msg_slave):
        self._conn.send(chatter.Data(
            module='HatMonitor',
            type='MsgSlave',
            data=common.msg_slave_to_sbs(msg_slave)))

    async def receive(self):
        msg = await self._conn.receive()
        msg_type = msg.data.module, msg.data.type
        assert msg_type == ('HatMonitor', 'MsgMaster')
        return common.msg_master_from_sbs(msg.data.data)


class Server(aio.Resource):

    def __init__(self):
        self._async_group = aio.Group()
        self._mid = 0
        self._local_components = []
        self._global_components = []
        self._change_cbs = util.CallbackRegistry()

    @property
    def async_group(self):
        return self._async_group

    @property
    def mid(self):
        return self._mid

    @property
    def local_components(self):
        return self._local_components

    @property
    def global_components(self):
        return self._global_components

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    def update(self, mid, global_components):
        assert mid == 0
        self._global_components = global_components
        self._local_components = [i._replace(mid=mid)
                                  for i in self._local_components]
        self._change_cbs.notify()

    def set_rank(self, cid, rank):
        assert False

    def set_local_components(self, local_components):
        self._local_components = [i._replace(mid=self.mid)
                                  for i in local_components]
        self._change_cbs.notify()


async def test_create(master_address):
    conf = {'address': master_address,
            'default_algorithm': 'BLESS_ALL',
            'group_algorithms': {}}

    master = await hat.monitor.server.master.create(conf)

    assert master.active is False

    conn = await connect(master_address)
    await conn.wait_closed()

    assert master.is_open

    await master.async_close()


async def test_set_server(master_address):
    conf = {'address': master_address,
            'default_algorithm': 'BLESS_ALL',
            'group_algorithms': {}}

    infos = [common.ComponentInfo(cid=i * 3,
                                  mid=i * 3 + 1,
                                  name=f'name{i}',
                                  group=f'group{i}',
                                  address=f'address{i}',
                                  rank=i * 3 + 2,
                                  blessing=None,
                                  ready=None)
             for i in range(10)]

    server = Server()

    changes = aio.Queue()

    def on_change():
        changes.put_nowait(master.components)

    master = await hat.monitor.server.master.create(conf)
    master.register_change_cb(on_change)

    assert not master.active

    await master.set_server(server)

    components = await changes.get()
    assert components == []
    assert master.active
    assert server.global_components == components

    server.set_local_components(infos)

    components = await changes.get()
    assert len(components) == len(infos)
    assert master.active
    assert server.global_components == components
    for info, component in zip(infos, components):
        assert component.mid == 0
        assert component.cid == info.cid
        assert component.name == info.name
        assert component.group == info.group
        assert component.address == info.address
        assert component.rank == info.rank
        assert component.blessing is not None
        assert component.ready == info.ready

    await master.set_server(None)

    components = await changes.get()
    assert components == []
    assert not master.active

    await master.set_server(server)

    components = await changes.get()
    assert components == []
    assert master.active

    components = await changes.get()
    assert len(components) == len(infos)
    assert master.active
    assert server.global_components == components

    await master.async_close()
    await server.async_close()


@pytest.mark.parametrize("slave_count", [1, 2, 5])
async def test_slaves(master_address, slave_count):
    conf = {'address': master_address,
            'default_algorithm': 'BLESS_ALL',
            'group_algorithms': {}}

    infos = [common.ComponentInfo(cid=i * 3,
                                  mid=i * 3 + 1,
                                  name=f'name{i}',
                                  group=f'group{i}',
                                  address=f'address{i}',
                                  rank=i * 3 + 2,
                                  blessing=None,
                                  ready=None)
             for i in range(3)]

    server = Server()
    master = await hat.monitor.server.master.create(conf)
    await master.set_server(server)

    conns = []
    for _ in range(slave_count):
        conn = await connect(master_address)
        conns.append(conn)

        msg = await conn.receive()
        assert msg.mid > 0
        assert msg.components == []

    for i, conn in enumerate(conns):
        msg = common.MsgSlave(infos)
        conn.send(msg)

        for conn in conns:
            msg = await conn.receive()
            assert len(msg.components) == len(infos) * (i + 1)

    assert len(master.components) == len(conns) * len(infos)

    while conns:
        conn, conns = conns[0], conns[1:]
        await conn.async_close()

        for conn in conns:
            msg = await conn.receive()
            assert len(msg.components) == len(infos) * len(conns)

    await master.async_close()
    await server.async_close()
