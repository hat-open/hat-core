import asyncio

import pytest

from hat import aio
from hat import chatter
from hat import util
from hat.monitor import common
import hat.monitor.client


pytestmark = pytest.mark.asyncio


@pytest.fixture
def server_port():
    return util.get_unused_tcp_port()


@pytest.fixture
def server_address(server_port):
    return f'tcp+sbs://127.0.0.1:{server_port}'


async def create_server(address):
    server = Server()
    server._conn_queue = aio.Queue()
    server._srv = await chatter.listen(
        common.sbs_repo, address,
        lambda conn: server._conn_queue.put_nowait(Connection(conn)))
    return server


class Server(aio.Resource):

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

    def send(self, msg_server):
        self._conn.send(chatter.Data(
            module='HatMonitor',
            type='MsgServer',
            data=common.msg_server_to_sbs(msg_server)))

    async def receive(self):
        msg = await self._conn.receive()
        msg_type = msg.data.module, msg.data.type
        assert msg_type == ('HatMonitor', 'MsgClient')
        return common.msg_client_from_sbs(msg.data.data)


async def test_client_connect_failure(server_address):
    conf = {'name': 'name',
            'group': 'group',
            'monitor_address': server_address,
            'component_address': None}

    with pytest.raises(ConnectionError):
        await hat.monitor.client.connect(conf)


async def test_client_connect(server_address):
    conf = {'name': 'name',
            'group': 'group',
            'monitor_address': server_address,
            'component_address': None}

    server = await create_server(server_address)
    client = await hat.monitor.client.connect(conf)
    conn = await server.get_connection()

    msg = await conn.receive()
    assert msg == common.MsgClient(name=conf['name'],
                                   group=conf['group'],
                                   address=conf['component_address'],
                                   ready=None)

    assert server.is_open
    assert client.is_open
    assert conn.is_open

    await server.async_close()
    await client.wait_closed()
    await conn.wait_closed()


async def test_client_set_ready(server_address):
    conf = {'name': 'name',
            'group': 'group',
            'monitor_address': server_address,
            'component_address': 'address'}

    server = await create_server(server_address)
    client = await hat.monitor.client.connect(conf)
    conn = await server.get_connection()

    msg = await conn.receive()
    assert msg == common.MsgClient(name=conf['name'],
                                   group=conf['group'],
                                   address=conf['component_address'],
                                   ready=None)

    client.set_ready(123)
    msg = await conn.receive()
    assert msg == common.MsgClient(name=conf['name'],
                                   group=conf['group'],
                                   address=conf['component_address'],
                                   ready=123)

    client.set_ready(123)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(conn.receive(), 0.001)

    client.set_ready(None)
    msg = await conn.receive()
    assert msg == common.MsgClient(name=conf['name'],
                                   group=conf['group'],
                                   address=conf['component_address'],
                                   ready=None)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(conn.receive(), 0.001)

    await client.async_close()
    await conn.wait_closed()
    await server.async_close()


async def test_client_change(server_address):
    conf = {'name': 'name',
            'group': 'group',
            'monitor_address': server_address,
            'component_address': 'address'}

    info = common.ComponentInfo(cid=1,
                                mid=2,
                                name='name',
                                group='group',
                                address='address',
                                rank=3,
                                blessing=4,
                                ready=5)

    server = await create_server(server_address)
    client = await hat.monitor.client.connect(conf)
    conn = await server.get_connection()

    changes = aio.Queue()
    client.register_change_cb(
        lambda: changes.put_nowait((client.info, client.components)))

    assert changes.empty()
    assert client.info is None
    assert client.components == []

    msg = common.MsgServer(cid=1, mid=2, components=[])
    conn.send(msg)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(changes.get(), 0.001)

    msg = common.MsgServer(cid=1, mid=2, components=[info])
    conn.send(msg)
    change_info, change_components = await changes.get()
    assert change_info == info
    assert change_components == [info]

    msg = common.MsgServer(cid=1, mid=2, components=[info._replace(cid=3)])
    conn.send(msg)
    change_info, change_components = await changes.get()
    assert change_info is None
    assert change_components == [info._replace(cid=3)]

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(changes.get(), 0.001)

    await client.async_close()
    await conn.wait_closed()
    await server.async_close()


async def test_component(server_address):
    conf = {'name': 'name',
            'group': 'group',
            'monitor_address': server_address,
            'component_address': 'address'}

    info = common.ComponentInfo(cid=1,
                                mid=2,
                                name='name',
                                group='group',
                                address='address',
                                rank=3,
                                blessing=None,
                                ready=None)

    running_queue = aio.Queue()

    async def async_run(component):
        running_queue.put_nowait(True)
        try:
            await asyncio.Future()
        finally:
            running_queue.put_nowait(False)

    server = await create_server(server_address)
    client = await hat.monitor.client.connect(conf)
    component = hat.monitor.client.Component(client, async_run)
    component.set_enabled(True)
    conn = await server.get_connection()

    msg = await conn.receive()
    assert msg.ready is None
    assert component.is_open
    assert running_queue.empty()

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=123)])
    conn.send(msg)
    msg = await conn.receive()
    assert msg.ready == 123
    assert component.is_open
    assert running_queue.empty()

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=123,
                                                     ready=123)])
    conn.send(msg)
    running = await running_queue.get()
    assert running is True
    assert component.is_open
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(conn.receive(), 0.001)

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=None,
                                                     ready=123)])
    conn.send(msg)
    msg = await conn.receive()
    assert msg.ready is None
    running = await running_queue.get()
    assert running is False

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=321,
                                                     ready=None)])
    conn.send(msg)
    msg = await conn.receive()
    assert msg.ready == 321
    assert component.is_open
    assert running_queue.empty()

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=321,
                                                     ready=321)])
    conn.send(msg)
    running = await running_queue.get()
    assert running is True
    assert component.is_open
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(conn.receive(), 0.001)

    await conn.async_close()
    running = await running_queue.get()
    assert running is False
    await component.wait_closed()

    await client.async_close()
    await server.async_close()
    assert running_queue.empty()


async def test_component_return(server_address):
    conf = {'name': 'name',
            'group': 'group',
            'monitor_address': server_address,
            'component_address': 'address'}

    info = common.ComponentInfo(cid=1,
                                mid=2,
                                name='name',
                                group='group',
                                address='address',
                                rank=3,
                                blessing=None,
                                ready=None)

    async def async_run(component):
        return

    server = await create_server(server_address)
    client = await hat.monitor.client.connect(conf)
    component = hat.monitor.client.Component(client, async_run)
    component.set_enabled(True)
    conn = await server.get_connection()

    msg = await conn.receive()
    assert msg.ready is None

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=123)])
    conn.send(msg)
    msg = await conn.receive()
    assert msg.ready == 123

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=123,
                                                     ready=123)])
    conn.send(msg)
    await component.wait_closed()

    await client.async_close()
    await conn.wait_closed()
    await server.async_close()


async def test_component_exception(server_address):
    conf = {'name': 'name',
            'group': 'group',
            'monitor_address': server_address,
            'component_address': 'address'}

    info = common.ComponentInfo(cid=1,
                                mid=2,
                                name='name',
                                group='group',
                                address='address',
                                rank=3,
                                blessing=None,
                                ready=None)

    async def async_run(component):
        raise Exception()

    server = await create_server(server_address)
    client = await hat.monitor.client.connect(conf)
    component = hat.monitor.client.Component(client, async_run)
    component.set_enabled(True)
    conn = await server.get_connection()

    msg = await conn.receive()
    assert msg.ready is None

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=123)])
    conn.send(msg)
    msg = await conn.receive()
    assert msg.ready == 123

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=123,
                                                     ready=123)])
    conn.send(msg)
    await component.wait_closed()

    await client.async_close()
    await conn.wait_closed()
    await server.async_close()


async def test_component_close_before_ready(server_address):
    conf = {'name': 'name',
            'group': 'group',
            'monitor_address': server_address,
            'component_address': 'address'}

    info = common.ComponentInfo(cid=1,
                                mid=2,
                                name='name',
                                group='group',
                                address='address',
                                rank=3,
                                blessing=None,
                                ready=None)

    async def async_run(component):
        await asyncio.Future()

    server = await create_server(server_address)
    client = await hat.monitor.client.connect(conf)
    component = hat.monitor.client.Component(client, async_run)
    component.set_enabled(True)
    conn = await server.get_connection()

    msg = await conn.receive()
    assert msg.ready is None

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=123)])
    conn.send(msg)
    msg = await conn.receive()
    assert msg.ready == 123

    await conn.async_close()
    await client.wait_closed()
    await component.wait_closed()

    await server.async_close()


async def test_component_enable(server_address):
    conf = {'name': 'name',
            'group': 'group',
            'monitor_address': server_address,
            'component_address': 'address'}

    info = common.ComponentInfo(cid=1,
                                mid=2,
                                name='name',
                                group='group',
                                address='address',
                                rank=3,
                                blessing=None,
                                ready=None)

    running_queue = aio.Queue()

    async def async_run(component):
        running_queue.put_nowait(True)
        try:
            await asyncio.Future()
        finally:
            running_queue.put_nowait(False)

    server = await create_server(server_address)
    client = await hat.monitor.client.connect(conf)
    component = hat.monitor.client.Component(client, async_run)
    conn = await server.get_connection()

    msg = await conn.receive()
    assert msg.ready is None

    msg = await conn.receive()
    assert msg.ready == 0

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=123,
                                                     ready=0)])
    conn.send(msg)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(conn.receive(), 0.001)
    assert running_queue.empty()

    component.set_enabled(True)

    msg = await conn.receive()
    assert msg.ready == 123

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=123,
                                                     ready=123)])
    conn.send(msg)

    running = await running_queue.get()
    assert running is True
    assert running_queue.empty()

    component.set_enabled(False)

    running = await running_queue.get()
    assert running is False
    assert running_queue.empty()

    msg = await conn.receive()
    assert msg.ready == 0

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=123,
                                                     ready=0)])
    conn.send(msg)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(conn.receive(), 0.001)
    assert running_queue.empty()

    msg = common.MsgServer(cid=1, mid=2,
                           components=[info._replace(blessing=None,
                                                     ready=0)])
    conn.send(msg)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(conn.receive(), 0.001)
    assert running_queue.empty()

    component.set_enabled(True)

    msg = await conn.receive()
    assert msg.ready is None

    await component.async_close()
    await client.async_close()
    await conn.wait_closed()
    await server.async_close()
