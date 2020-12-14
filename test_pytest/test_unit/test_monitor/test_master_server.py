import asyncio
import pytest
import collections

from hat import aio
from hat import util
import hat.monitor.client
import hat.monitor.common
import hat.monitor.server.master
import hat.monitor.server.server


@pytest.fixture
def master_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def server_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def master_conf(master_port):
    return {'address': f'tcp+sbs://127.0.0.1:{master_port}',
            'parents': [],
            'default_algorithm': 'BLESS_ALL',
            'group_algorithms': {'bless_all_group': 'BLESS_ALL',
                                 'bless_one_group': 'BLESS_ONE'}}


@pytest.fixture
def server_conf(server_port):
    return {'address': f'tcp+sbs://127.0.0.1:{server_port}',
            'default_rank': 1}


@pytest.fixture
async def master(master_conf):
    group = aio.Group()
    queue = aio.Queue()

    group.spawn(hat.monitor.server.master.run, master_conf,
                lambda m: queue.put_nowait(m))
    master = await queue.get()
    assert master is not None

    yield master

    await group.async_close()
    master = await queue.get()
    assert master is None
    assert queue.empty()


@pytest.fixture
async def server(server_conf, master):
    server = await hat.monitor.server.server.create(server_conf)
    server.set_master(master)

    yield server

    await server.async_close()
    assert server.is_closed


@pytest.fixture
def get_components(master, server):
    master_queue, server_queue = aio.Queue(), aio.Queue()
    master.register_change_cb(
        lambda: master_queue.put_nowait(master.components))
    server.register_change_cb(
        lambda: server_queue.put_nowait(server.components))

    async def get_next():
        master_components, server_components = await asyncio.gather(
            master_queue.get(), server_queue.get())
        assert master_components == server_components
        return master_components

    return get_next


async def create_client(monitor_address, name='client',
                        group='group'):
    return await hat.monitor.client.connect({
        'name': name,
        'group': group,
        'monitor_address': monitor_address,
        'component_address': None})


@pytest.mark.asyncio
async def test_master(master):
    assert not master.is_closed
    assert master.mid == 0
    assert master.components == []


@pytest.mark.asyncio
async def test_server(server):
    assert not server.is_closed
    assert server.mid == 0
    assert server.components == []


@pytest.mark.asyncio
async def test_server_without_master(server):
    server.set_master(None)
    assert not server.is_closed
    assert server.mid == 0
    assert server.components == []


@pytest.mark.asyncio
async def test_connect(server_conf, get_components):
    client = await create_client(server_conf['address'])

    components = await get_components()
    assert len(components) == 1

    await client.async_close()

    components = await get_components()
    assert components == []


@pytest.mark.parametrize("client_count", [1, 2, 5])
@pytest.mark.asyncio
async def test_multiple_clients(server_conf, get_components,
                                client_count):
    clients = collections.deque()

    for i in range(client_count):
        client = await create_client(server_conf['address'], name=f'client{i}')
        clients.append(client)
        components = await get_components()
        assert len(components) == i + 1

    for i in reversed(range(client_count)):
        client = clients.popleft()
        await client.async_close()
        components = await get_components()
        assert len(components) == i


@pytest.mark.asyncio
async def test_set_rank(server_conf, server, get_components):
    client = await create_client(server_conf['address'])

    components = await get_components()
    assert len(components) == 1
    assert components[0].rank == server_conf['default_rank']

    cid, mid = components[0].cid, components[0].mid
    server.set_rank(cid, mid, server_conf['default_rank'] + 1)

    components = await get_components()
    assert len(components) == 1
    assert components[0].rank == server_conf['default_rank'] + 1

    await client.async_close()

    components = await get_components()
    assert components == []

    client = await create_client(server_conf['address'])

    components = await get_components()
    assert len(components) == 1
    assert components[0].rank == server_conf['default_rank'] + 1

    await client.async_close()

    components = await get_components()
    assert components == []


@pytest.mark.parametrize("client_count", [1, 2, 5])
@pytest.mark.asyncio
async def test_bless_one(server_conf, get_components, client_count):
    clients = []

    for i in range(client_count):
        client = await create_client(server_conf['address'],
                                     name=f'client{i}',
                                     group='bless_one_group')
        clients.append(client)

        components = await get_components()
        blessed = sum(1 for i in components if i.blessing is not None)
        assert blessed == 1

    await asyncio.gather(*[client.async_close() for client in clients])


@pytest.mark.parametrize("client_count", [1, 2, 5])
@pytest.mark.asyncio
async def test_bless_all(server_conf, get_components, client_count):
    clients = []

    for i in range(client_count):
        client = await create_client(server_conf['address'],
                                     name=f'client{i}',
                                     group='bless_all_group')
        clients.append(client)

        components = await get_components()
        assert all(i.blessing is not None for i in components)

    await asyncio.gather(*[client.async_close() for client in clients])


@pytest.mark.asyncio
async def test_change_blessing_with_rank(server_conf, server, get_components):
    client1 = await create_client(server_conf['address'],
                                  name='c1',
                                  group='bless_one_group')

    components = await get_components()
    c1 = util.first(components, lambda c: c.name == 'c1')
    assert c1.rank == 1
    assert c1.blessing is not None

    client2 = await create_client(server_conf['address'],
                                  name='c2',
                                  group='bless_one_group')

    components = await get_components()
    c1 = util.first(components, lambda c: c.name == 'c1')
    c2 = util.first(components, lambda c: c.name == 'c2')
    assert c1.rank == 1
    assert c1.blessing is not None
    assert c2.rank == 1
    assert c2.blessing is None

    server.set_rank(c2.cid, c2.mid, 0)

    components = await get_components()
    c1 = util.first(components, lambda c: c.name == 'c1')
    c2 = util.first(components, lambda c: c.name == 'c2')
    assert c1.rank == 1
    assert c1.blessing is None
    assert c2.rank == 0
    assert c2.blessing is not None

    await client1.async_close()
    await client2.async_close()


@pytest.mark.asyncio
async def test_rank_not_changing(server_conf, server,
                                 get_components):
    client1 = await create_client(server_conf['address'],
                                  name='c1',
                                  group='bless_one_group')

    components = await get_components()
    new_c1 = util.first(components, lambda c: c.name == 'c1')
    assert new_c1.rank is not None

    client2 = await create_client(server_conf['address'],
                                  name='c2',
                                  group='bless_one_group')

    components = await get_components()
    old_c1, new_c1 = new_c1, util.first(components, lambda c: c.name == 'c1')
    assert new_c1.rank == old_c1.rank

    await client2.async_close()

    components = await get_components()
    old_c1, new_c1 = new_c1, util.first(components, lambda c: c.name == 'c1')
    assert new_c1.rank == old_c1.rank

    await client1.async_close()
