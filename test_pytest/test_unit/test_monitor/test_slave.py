import asyncio

import pytest

from hat import aio
from hat import chatter
from hat import util
from hat.monitor.server import common
import hat.monitor.server.server
import hat.monitor.server.slave
import hat.monitor.server.master


pytestmark = pytest.mark.asyncio


@pytest.fixture
def primary_port():
    return util.get_unused_tcp_port()


@pytest.fixture
def secondary_port(primary_port):
    port = None
    while not port or port == primary_port:
        port = util.get_unused_tcp_port()
    return port


@pytest.fixture
def primary_address(primary_port):
    return f'tcp+sbs://127.0.0.1:{primary_port}'


@pytest.fixture
def secondary_address(secondary_port):
    return f'tcp+sbs://127.0.0.1:{secondary_port}'


@pytest.fixture
def patch_connect_timeout(monkeypatch):
    monkeypatch.setattr(hat.monitor.server.slave, 'connect_timeout', 0.1)


@pytest.fixture
def patch_connect_retry_delay(monkeypatch):
    monkeypatch.setattr(hat.monitor.server.slave, 'connect_retry_delay', 0.1)


async def create_master(address):
    master = Master()
    master._conn_queue = aio.Queue()
    master._srv = await chatter.listen(
        common.sbs_repo, address,
        lambda conn: master._conn_queue.put_nowait(Connection(conn)))
    return master


class Master(aio.Resource):

    @property
    def async_group(self):
        return self._srv.async_group

    async def get_connection(self):
        return await self._conn_queue.get()


class Connection(aio.Resource):

    def __init__(self, conn):
        self._conn = conn

    @property
    def async_group(self):
        return self._conn.async_group

    def send(self, msg_master):
        self._conn.send(chatter.Data(
            module='HatMonitor',
            type='MsgMaster',
            data=common.msg_master_to_sbs(msg_master)))

    async def receive(self):
        msg = await self._conn.receive()
        msg_type = msg.data.module, msg.data.type
        assert msg_type == ('HatMonitor', 'MsgSlave')
        return common.msg_slave_from_sbs(msg.data.data)


class Server(aio.Resource):

    def __init__(self):
        self._async_group = aio.Group()
        self._mid_queue = aio.Queue()
        self._global_components_queue = aio.Queue()
        self._local_components_queue = aio.Queue()
        self._mid = 0
        self._local_components = []
        self._global_components = []
        self._change_cbs = util.CallbackRegistry()

    @property
    def mid_queue(self):
        return self._mid_queue

    @property
    def global_components_queue(self):
        return self._global_components_queue

    @property
    def local_components_queue(self):
        return self._local_components_queue

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
        if mid != self._mid:
            self._mid = mid
            self._mid_queue.put_nowait(mid)
        if global_components != self._global_components:
            self._global_components = global_components
            self._global_components_queue.put_nowait(global_components)
        local_components = [i._replace(mid=mid)
                            for i in self._local_components]
        if local_components != self._local_components:
            self._local_components = local_components
            self._local_components_queue.put_nowait(local_components)
        self._change_cbs.notify()

    def set_rank(self, cid, rank):
        assert False

    def set_local_components(self, local_components):
        local_components = [i._replace(mid=self.mid)
                            for i in local_components]
        if local_components != self._local_components:
            self._local_components = local_components
            self._local_components_queue.put_nowait(local_components)
        self._change_cbs.notify()


async def test_connect(patch_connect_timeout, patch_connect_retry_delay,
                       primary_address, secondary_address):
    master = await create_master(primary_address)

    conn = await hat.monitor.server.slave.connect(
        addresses=[secondary_address] * 3,
        retry_count=3)
    assert conn is None

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(hat.monitor.server.slave.connect(
            addresses=[secondary_address] * 3,
            retry_count=None), 0.2)

    conn = await hat.monitor.server.slave.connect(
        addresses=[secondary_address, primary_address],
        retry_count=3)
    assert conn is not None
    assert conn.is_open
    await conn.async_close()

    await master.async_close()


async def test_slave(primary_address):
    info = common.ComponentInfo(cid=1,
                                mid=2,
                                name='name',
                                group='group',
                                address='address',
                                rank=3,
                                blessing=None,
                                ready=None)

    server = Server()
    master = await create_master(primary_address)
    slave = await hat.monitor.server.slave.connect(addresses=[primary_address],
                                                   retry_count=3)
    slave = hat.monitor.server.slave.Slave(server, slave)
    conn = await master.get_connection()

    assert server.mid_queue.empty()
    assert server.global_components_queue.empty()
    assert server.local_components_queue.empty()

    msg = common.MsgMaster(mid=123,
                           components=[info])
    conn.send(msg)

    mid = await server.mid_queue.get()
    assert mid == msg.mid

    components = await server.global_components_queue.get()
    assert components == [info]

    msg = await conn.receive()
    assert msg.components == []

    server.set_local_components([info])

    msg = await conn.receive()
    assert msg.components == [info._replace(mid=123)]

    await master.async_close()
    await slave.wait_closed()


async def test_run(patch_connect_timeout, patch_connect_retry_delay,
                   primary_address, secondary_address):
    primary_master_conf = {'address': primary_address,
                           'default_algorithm': 'BLESS_ALL',
                           'group_algorithms': {}}
    secondary_master_conf = {'address': secondary_address,
                             'default_algorithm': 'BLESS_ALL',
                             'group_algorithms': {}}

    primary_slave_conf = {'parents': []}
    secondary_slave_conf = {'parents': [primary_address]}

    primary_server = Server()
    secondary_server = Server()

    primary_master = await hat.monitor.server.master.create(
        primary_master_conf)
    primary_run = asyncio.ensure_future(
        hat.monitor.server.slave.run(primary_slave_conf, primary_server,
                                     primary_master))

    secondary_master = await hat.monitor.server.master.create(
        secondary_master_conf)
    secondary_run = asyncio.ensure_future(
        hat.monitor.server.slave.run(secondary_slave_conf, secondary_server,
                                     secondary_master))

    mid = await secondary_server.mid_queue.get()
    assert mid > 0
    assert primary_server.mid == 0
    assert not secondary_master.active

    primary_run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await primary_run
    await primary_master.async_close()

    while not secondary_master.active:
        await asyncio.sleep(0.001)
    mid = await secondary_server.mid_queue.get()
    assert mid == 0

    primary_master = await hat.monitor.server.master.create(
        primary_master_conf)
    primary_run = asyncio.ensure_future(
        hat.monitor.server.slave.run(primary_slave_conf, primary_server,
                                     primary_master))

    mid = await secondary_server.mid_queue.get()
    assert mid > 0
    assert primary_server.mid == 0
    assert not secondary_master.active

    secondary_run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await secondary_run
    await secondary_master.async_close()

    await primary_master.async_close()
    await primary_run
