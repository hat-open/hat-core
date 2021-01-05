import pytest
import asyncio

import hat.monitor.common
import hat.monitor.server.main
import hat.monitor.client

from hat import aio

from test_unit.test_monitor import common


class MockError(Exception):
    pass


@pytest.fixture
async def async_group():
    group = aio.Group()
    yield group
    await group.async_close()


@pytest.fixture
async def monitor_server_factory(async_group, tmpdir, unused_tcp_port_factory):

    async def f(parents=[], rank=1, algorithm='BLESS_ALL'):
        group = async_group.create_subgroup()
        address = f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}'
        monitor_server_conf = {
            'server': {
                'address': address,
                'default_rank': rank},
            'master': {
                'address': f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}',
                'parents': parents,
                'default_algorithm': algorithm,
                'group_algorithms': {}},
            'ui': {
                'address': f'http://127.0.0.1:{unused_tcp_port_factory()}'}}
        group.spawn(hat.monitor.server.main.async_main, monitor_server_conf,
                    tmpdir)
        await asyncio.sleep(0.01)  # Wait for monitor server to start listening
        return group, address

    return f


@pytest.mark.asyncio
async def test_run_component(async_group, unused_tcp_port_factory):

    running_queue = aio.Queue()

    async def run_cb(_):
        running_queue.put_nowait(True)
        try:
            while True:
                await asyncio.sleep(1)
        finally:
            running_queue.put_nowait(False)

    address = f'tcp+sbs://localhost:{unused_tcp_port_factory()}'
    server_conf = {'address': address,
                   'default_rank': 1}
    server = await hat.monitor.server.server.create(server_conf)
    master = common.create_master()
    server.set_master(master)

    client_conf = {'name': 'client',
                   'group': 'client',
                   'monitor_address': address,
                   'component_address': None}
    async_group.spawn(hat.monitor.client.run_component, client_conf, run_cb)

    assert running_queue.empty()

    components = []
    while not components:
        components = await master._components_queue.get()
    assert len(components) == 1
    c = components[0]
    assert (c.name == 'client' and
            c.group == 'client' and
            c.address is None and
            c.blessing is None and
            c.ready is None)
    assert running_queue.empty()

    master._set_components([c._replace(blessing=3)])
    components = await master._components_queue.get()
    c = components[0]
    assert c.ready == 3
    assert running_queue.empty()

    master._set_components([c._replace(blessing=3)])
    assert (await running_queue.get()) is True

    master._set_components([c._replace(blessing=None)])
    assert (await running_queue.get()) is False
    components = await master._components_queue.get()
    c = components[0]
    assert c.ready is None

    master._set_components([c._replace(blessing=4)])
    components = await master._components_queue.get()
    c = components[0]
    assert c.ready == 4
    assert running_queue.empty()

    master._set_components([c._replace(blessing=4)])
    assert (await running_queue.get()) is True

    master._set_components([c._replace(blessing=5)])
    assert (await running_queue.get()) is False
    components = await master._components_queue.get()
    c = components[0]
    assert c.ready != 4


@pytest.mark.skip(reason="WIP regresion failure")
@pytest.mark.asyncio
async def test_run_component_result(async_group, monitor_server_factory):

    async def run_cb(_):
        return 'test'

    _, address = await monitor_server_factory()

    client_conf = {'name': 'client',
                   'group': 'client',
                   'monitor_address': address,
                   'component_address': None}
    future = async_group.spawn(hat.monitor.client.run_component, client_conf,
                               run_cb)

    assert (await future) == 'test'


@pytest.mark.skip(reason="WIP regresion failure")
@pytest.mark.asyncio
async def test_run_component_exception(async_group, monitor_server_factory):

    async def run_cb(_):
        raise MockError()

    _, address = await monitor_server_factory()

    client_conf = {'name': 'client',
                   'group': 'client',
                   'monitor_address': address,
                   'component_address': None}
    future = async_group.spawn(hat.monitor.client.run_component, client_conf,
                               run_cb)

    with pytest.raises(MockError):
        await future


@pytest.mark.skip(reason="WIP regresion failure")
@pytest.mark.asyncio
async def test_components_run_serial(async_group, monitor_server_factory):

    async def run_cb(_):
        return

    _, address = await monitor_server_factory(algorithm='BLESS_ONE')

    client_conf = {'name': 'client',
                   'group': 'client',
                   'monitor_address': address,
                   'component_address': None}

    for i in range(3):
        await hat.monitor.client.run_component(client_conf, run_cb)
