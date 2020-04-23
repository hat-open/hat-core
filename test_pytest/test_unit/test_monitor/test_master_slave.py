import pytest
import collections
import asyncio

from hat.util import aio
import hat.monitor.server.master
import hat.monitor.server.server
import hat.monitor.client
import hat.monitor.common


@pytest.fixture
def short_timeout(monkeypatch):
    module = hat.monitor.server.master
    monkeypatch.setattr(module, 'connect_retry_delay', 0.001)
    monkeypatch.setattr(module, 'connect_retry_count', 1)
    monkeypatch.setattr(module, 'connected_timeout', 0.01)


@pytest.fixture(scope="session")
def sbs_repo():
    return hat.monitor.common.create_sbs_repo()


@pytest.fixture
async def async_group():
    group = aio.Group()
    yield group
    await group.async_close()


def create_master_queue(sbs_repo, async_group, address, parents,
                        default_algorithm='BLESS_ALL',
                        group_algorithms={}):
    conf = {'address': address,
            'parents': parents,
            'default_algorithm': default_algorithm,
            'group_algorithms': group_algorithms}
    queue = aio.Queue()
    async_group.spawn(hat.monitor.server.master.run, conf, sbs_repo,
                      lambda master: queue.put_nowait(master))
    return queue


async def create_monitor_group(sbs_repo, server_address, master_address,
                               master_parents,
                               default_algorithm='BLESS_ALL',
                               group_algorithms={}):
    server_conf = {'address': server_address,
                   'default_rank': 1}
    master_conf = {'address': master_address,
                   'parents': master_parents,
                   'default_algorithm': default_algorithm,
                   'group_algorithms': group_algorithms}

    group = aio.Group()
    server = await hat.monitor.server.server.create(server_conf, sbs_repo)

    async def run():
        master_run_future = group.spawn(hat.monitor.server.master.run,
                                        master_conf, sbs_repo,
                                        server.set_master)
        try:
            await asyncio.wait([server.closed, master_run_future],
                               return_when=asyncio.FIRST_COMPLETED)
        finally:
            group.close()
            await aio.uncancellable(server.async_close())

    group.spawn(run)
    return group


def create_address(unused_tcp_port_factory):
    return f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}'


async def wait_master(queue, is_local):
    cls = (hat.monitor.server.master.LocalMaster if is_local
           else hat.monitor.server.master.RemoteMaster)
    while True:
        master = await queue.get()
        if isinstance(master, cls):
            return master


async def wait_client(client, is_master, components_count):
    while (not client.info or
            (is_master and client.info.mid != 0) or
            (not is_master and client.info.mid == 0) or
            (len(client.components) != components_count)):
        await asyncio.sleep(0.001)


@pytest.mark.parametrize("master_count", [1, 2, 5])
@pytest.mark.asyncio
async def test_connect(sbs_repo, short_timeout, async_group,
                       unused_tcp_port_factory, master_count):
    address_group_queue_cache = collections.deque()

    for i in range(master_count):
        addresses = [address for address, _, _ in address_group_queue_cache]
        address = create_address(unused_tcp_port_factory)
        group = async_group.create_subgroup()
        queue = create_master_queue(sbs_repo, group, address, addresses)

        master = await asyncio.wait_for(wait_master(queue, i == 0), 0.1)
        if i == 0:
            assert master.mid == 0
        else:
            assert master.mid != 0

        address_group_queue_cache.append((address, group, queue))

    while address_group_queue_cache:
        _, group, queue = address_group_queue_cache.popleft()
        assert queue.empty()
        await group.async_close()

        for i, (_, __, queue) in enumerate(address_group_queue_cache):
            await asyncio.wait_for(wait_master(queue, i == 0), 10)


@pytest.mark.parametrize("monitor_count", [1, 2, 5])
@pytest.mark.parametrize("client_count", [1, 2, 5])
@pytest.mark.asyncio
async def test_clients(sbs_repo, short_timeout, async_group,
                       unused_tcp_port_factory, monitor_count, client_count):

    monitors = collections.deque()

    for i in range(monitor_count):
        server_address = create_address(unused_tcp_port_factory)
        master_address = create_address(unused_tcp_port_factory)
        group = await create_monitor_group(sbs_repo, server_address,
                                           master_address,
                                           [i for i, _, __ in monitors])
        clients = []
        for j in range(client_count):
            client_conf = {'name': f'client_{i}_{j}',
                           'group': 'group1',
                           'monitor_address': server_address,
                           'component_address': None}
            client = await hat.monitor.client.connect(client_conf, sbs_repo)
            clients.append(client)

        monitors.append((master_address, group, clients))

    while monitors:
        for i, (_, __, clients) in enumerate(monitors):
            for client in clients:
                await asyncio.wait_for(
                    wait_client(client, i == 0, len(monitors) * client_count),
                    10)

        _, group, clients = monitors.popleft()
        await asyncio.wait([client.async_close() for client in clients])
        await group.async_close()
