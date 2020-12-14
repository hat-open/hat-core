import pytest

import hat.monitor.common
import hat.monitor.client
import hat.monitor.server.master
import hat.monitor.server.server
from hat.monitor.common import ComponentInfo

from hat import aio
from test_unit.test_monitor import common


@pytest.fixture
def server_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def server_conf(server_port):
    return {
        'address': f'tcp+sbs://localhost:{server_port}',
        'default_rank': 1}


@pytest.fixture
def client_conf(server_port):
    return {
        'name': 'c1',
        'group': 'g1',
        'monitor_address': f'tcp+sbs://localhost:{server_port}',
        'component_address': None}


@pytest.mark.asyncio
async def test_client_connect_disconnect(server_conf, client_conf):
    components_queue = aio.Queue()
    server = await hat.monitor.server.server.create(server_conf)
    server.register_change_cb(
        lambda: components_queue.put_nowait(server.components))
    client = await hat.monitor.client.connect(client_conf)
    components = await components_queue.get()
    assert len(components) == 1
    c = components[0]
    assert (c.mid == server.mid and
            c.name == client_conf['name'] and
            c.group == client_conf['group'] and
            c.address == client_conf['component_address'] and
            c.rank == server_conf['default_rank'] and
            c.blessing is None and
            c.ready is None)
    await client.async_close()
    assert client.is_closed
    assert await components_queue.get() == []
    await server.async_close()
    assert server.is_closed


@pytest.mark.asyncio
async def test_client_set_ready(server_conf, client_conf):
    components_queue = aio.Queue()
    server = await hat.monitor.server.server.create(server_conf)
    server.register_change_cb(
        lambda: components_queue.put_nowait(server.components))
    client = await hat.monitor.client.connect(client_conf)
    assert (await components_queue.get())[0].ready is None
    client.set_ready(5)
    assert (await components_queue.get())[0].ready == 5
    client.set_ready(7)
    assert (await components_queue.get())[0].ready == 7
    client.set_ready(None)
    assert (await components_queue.get())[0].ready is None
    client.set_ready(-3)
    assert (await components_queue.get())[0].ready == -3
    await client.async_close()
    assert client.is_closed
    await server.async_close()
    assert server.is_closed


@pytest.mark.asyncio
async def test_server_set_rank(server_conf, client_conf):
    components_queue = aio.Queue()
    server = await hat.monitor.server.server.create(server_conf)
    server.register_change_cb(
        lambda: components_queue.put_nowait(server.components))
    client = await hat.monitor.client.connect(client_conf)
    c = (await components_queue.get())[0]
    assert c.rank == 1
    server.set_rank(c.cid, c.mid, 2)
    assert (await components_queue.get())[0].rank == 2
    server.set_rank(c.cid, c.mid, -11)
    assert (await components_queue.get())[0].rank == -11
    await client.async_close()
    assert client.is_closed
    await server.async_close()
    assert server.is_closed


@pytest.mark.asyncio
async def test_server_set_rank_nonexistent(server_conf):
    server = await hat.monitor.server.server.create(server_conf)
    server.set_rank(1, server.mid, 2)
    await server.async_close()
    assert server.is_closed


@pytest.mark.asyncio
async def test_server_rank_cache(server_conf, client_conf):

    async def client_connect_info_queue():
        info_queue = aio.Queue()
        client = await hat.monitor.client.connect(client_conf)
        client.register_change_cb(lambda: info_queue.put_nowait(client.info))
        return client, info_queue

    async def get_info_until_not_none(info_queue):
        info = None
        while info is None:
            info = await info_queue.get()
        return info

    server = await hat.monitor.server.server.create(server_conf)
    client, info_queue = await client_connect_info_queue()
    info = await get_info_until_not_none(info_queue)
    assert info.rank == 1
    server.set_rank(info.cid, info.mid, 2)
    assert (await info_queue.get()).rank == 2
    await client.async_close()
    assert client.is_closed

    client, info_queue = await client_connect_info_queue()
    info = await get_info_until_not_none(info_queue)
    assert info.rank == 2

    master = common.create_master(mid=server.mid, components=[
        server.components[0]._replace(rank=3)])

    server.set_master(master)
    assert (await info_queue.get()).rank == 3
    await client.async_close()
    assert client.is_closed
    server.set_master(None)

    client, info_queue = await client_connect_info_queue()
    info = await get_info_until_not_none(info_queue)
    assert info.rank == 3

    master = common.create_master(mid=server.mid, components=[
        server.components[0]._replace(rank=4)])

    server.set_master(master)
    assert (await info_queue.get()).rank == 4
    master._set_components([i._replace(rank=5) for i in master.components])
    assert (await info_queue.get()).rank == 5
    await client.async_close()
    assert client.is_closed
    server.set_master(None)

    client, info_queue = await client_connect_info_queue()
    info = await get_info_until_not_none(info_queue)
    assert info.rank == 5
    await client.async_close()
    assert client.is_closed


@pytest.mark.asyncio
async def test_server_set_master_mid_component(server_conf):
    c1 = ComponentInfo(cid=1, mid=10, name='c1', group='g1', address=None,
                       rank=1, blessing=None, ready=None)
    c2 = ComponentInfo(cid=2, mid=11, name='c2', group='g2', address='1.2.3.4',
                       rank=2, blessing=3, ready=3)
    server_change_queue = aio.Queue()
    server = await hat.monitor.server.server.create(server_conf)
    server.register_change_cb(lambda: server_change_queue.put_nowait((None)))
    assert server.mid == 0 and server.components == []
    master = common.create_master(mid=5, components=[c1, c2])
    server.set_master(master)
    await server_change_queue.get()
    assert server.mid == 5 and server.components == [c1, c2]
    master._set_mid(3)
    await server_change_queue.get()
    assert server.mid == 3 and server.components == [c1, c2]
    master._set_components([c2])
    await server_change_queue.get()
    assert server.mid == 3 and server.components == [c2]
    server.set_master(None)
    await server_change_queue.get()
    assert server.mid == 0 and server.components == []
    await server.async_close()
    assert server.is_closed


@pytest.mark.asyncio
async def test_server_master_set_rank(server_conf):
    server = await hat.monitor.server.server.create(server_conf)
    master = common.create_master()
    server.set_master(master)
    server.set_rank(1, 0, 10)
    assert (await master._rank_queue.get()) == (1, 0, 10)
    server.set_rank(3, 2, 5)
    assert (await master._rank_queue.get()) == (3, 2, 5)
    await server.async_close()
    assert server.is_closed


@pytest.mark.asyncio
async def test_client_server_master(server_conf, client_conf):
    c2 = ComponentInfo(cid=2, mid=1, name='c2', group='g2', address='1.2.3.4',
                       rank=2, blessing=3, ready=3)
    client_change_queue = aio.Queue()
    server = await hat.monitor.server.server.create(server_conf)
    client = await hat.monitor.client.connect(client_conf)
    client.register_change_cb(lambda: client_change_queue.put_nowait(None))
    master = common.create_master(mid=1, components=[])

    client_info = None
    while client_info is None:
        await client_change_queue.get()
        client_info = client.info

    server_components = server.components
    server.set_master(master)
    await client_change_queue.get()
    assert client.components == master.components and client.info is None

    local_components = await master._components_queue.get()
    assert (len(local_components) == 1 and
            local_components == [i._replace(mid=master.mid)
                                 for i in server_components])
    c1 = local_components[0]._replace(mid=1, rank=7)
    master._set_components([c1, c2])
    assert server.components == master.components
    await client_change_queue.get()
    assert client.components == master.components and client.info == c1

    client.set_ready(12)
    local_components = await master._components_queue.get()
    assert len(local_components) == 1 and local_components[0].ready == 12
    c1 = local_components[0]._replace(mid=1, ready=12, blessing=34)
    master._set_components([c1, c2])
    assert server.components == master.components
    await client_change_queue.get()
    assert client.info == c1 and client.components == master.components

    master._set_mid(2)
    await client_change_queue.get()
    assert client.info.mid == 2

    server.set_master(None)
    await client_change_queue.get()
    assert client.info.mid == 0 and client.components == [client.info]

    await client.async_close()
    assert client.is_closed
    await server.async_close()
    assert server.is_closed
