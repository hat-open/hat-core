import pytest
import asyncio
import functools

import hat.monitor.common
import hat.monitor.client
import hat.monitor.server.main
import hat.event.client
import hat.event.common
import hat.event.server.communication

from hat.util import aio
from test_unit.test_event import common


class MockError(Exception):
    pass


@pytest.fixture
def short_client_reconnect_delay(monkeypatch):
    module = hat.event.client
    monkeypatch.setattr(module, 'reconnect_delay', 0.01)


@pytest.fixture
async def async_group():
    group = aio.Group()
    yield group
    await group.async_close()


@pytest.fixture
async def monitor_server(async_group, unused_tcp_port_factory, tmpdir):
    address = f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}'
    monitor_server_conf = {
        'server': {
            'address': address,
            'default_rank': 1},
        'master': {
            'address': f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}',
            'parents': [],
            'default_algorithm': 'BLESS_ALL',
            'group_algorithms': {'event': 'BLESS_ONE'}},
        'ui': {
            'address': f'http://127.0.0.1:{unused_tcp_port_factory()}'}}
    async_group.spawn(hat.monitor.server.main.async_main, monitor_server_conf,
                      tmpdir)
    await asyncio.sleep(0.01)  # Wait for monitor server to start listening
    return address


@pytest.fixture
def event_server_factory(async_group, monitor_server, unused_tcp_port_factory):
    i = 0

    def f():
        nonlocal i
        event_server_addr = f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}'
        event_server_conf = {'name': f'event_server_{i}',
                             'group': 'event_server',
                             'monitor_address': monitor_server,
                             'component_address': event_server_addr}
        i += 1
        group = async_group.create_subgroup()
        run_cb = functools.partial(event_server_run_cb, event_server_addr)
        future = group.spawn(hat.monitor.client.run_component,
                             event_server_conf, run_cb)
        return group, future

    return f


async def event_server_run_cb(address, monitor_client):
    conf = {'address': address}
    engine = common.create_module_engine(register_cb=lambda events: [
        common.process_event_to_event(i) for i in events])
    comm = await hat.event.server.communication.create(conf, engine)
    try:
        await asyncio.wait([engine.closed, comm.closed],
                           return_when=asyncio.FIRST_COMPLETED)
    finally:
        await comm.async_close()
        await engine.async_close()


@pytest.fixture
def client_factory(async_group, monitor_server):
    i = 0

    def f(run_cb):
        nonlocal i
        event_client_conf = {'name': f'client_{i}',
                             'group': 'client',
                             'monitor_address': monitor_server,
                             'component_address': None}
        i += 1
        group = async_group.create_subgroup()
        wrapped_run_cb = functools.partial(client_run_cb, 'event_server',
                                           run_cb)
        future = group.spawn(hat.monitor.client.run_component,
                             event_client_conf, wrapped_run_cb)
        return group, future

    return f


async def client_run_cb(server_group, run_cb, monitor_client):
    return await hat.event.client.run_client(monitor_client,
                                             server_group, run_cb)


@pytest.mark.parametrize("server_count", [1, 2, 10])
@pytest.mark.asyncio
async def test_run_client(event_server_factory, client_factory,
                          short_client_reconnect_delay, server_count):
    client_queue = aio.Queue()

    async def run_cb(event_client):
        client_queue.put_nowait(event_client)
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            client_queue.put_nowait(None)
            raise

    client_factory(run_cb)

    for i in range(server_count):
        server_group, _ = event_server_factory()

        event_client = await client_queue.get()
        assert event_client is not None

        register_events = [hat.event.common.RegisterEvent(
            event_type=[str(i)],
            source_timestamp=None,
            payload=None)]
        events = await event_client.register_with_response(register_events)
        assert all(common.compare_register_event_vs_event(r, e)
                   for r, e in zip(register_events, events))

        await server_group.async_close()

        assert (await client_queue.get()) is None


@pytest.mark.asyncio
async def test_run_client_result(event_server_factory, client_factory,
                                 short_client_reconnect_delay):

    async def run_cb(event_client):
        return 'test'

    event_server_factory()
    _, client_future = client_factory(run_cb)

    assert (await client_future) == 'test'


@pytest.mark.asyncio
async def test_run_client_exception(event_server_factory, client_factory,
                                    short_client_reconnect_delay):

    async def run_cb(event_client):
        raise MockError()

    event_server_factory()
    _, client_future = client_factory(run_cb)

    with pytest.raises(MockError):
        await client_future


@pytest.mark.parametrize("run_count", [1, 2, 10])
@pytest.mark.asyncio
async def test_run_client_close_from_cb(event_server_factory, client_factory,
                                        run_count,
                                        short_client_reconnect_delay):
    n = 0

    async def run_cb(event_client):
        nonlocal n
        n += 1
        if n == run_count:
            return 'test'
        else:
            await event_client.async_close()

    event_server_factory()
    _, client_future = client_factory(run_cb)

    assert (await client_future) == 'test'
    assert n == run_count


@pytest.mark.parametrize("run_count", [1, 2, 10])
@pytest.mark.asyncio
async def test_run_client_cancel_cb(event_server_factory, client_factory,
                                    run_count, short_client_reconnect_delay):
    n = 0

    async def run_cb(event_client):
        nonlocal n
        n += 1
        if n == run_count:
            return 'test'
        else:
            raise asyncio.CancelledError

    event_server_factory()
    _, client_future = client_factory(run_cb)

    assert (await client_future) == 'test'
    assert n == run_count


@pytest.mark.asyncio
async def test_run_client_change_while_connecting(
        async_group, unused_tcp_port_factory, monitor_server,
        event_server_factory, client_factory, short_client_reconnect_delay):

    async def run_decoy_cb(_):
        await asyncio.sleep(0.1)

    async def run_cb(_):
        return 'test'

    _, client_future = client_factory(run_cb)

    decoy_address = f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}'
    decoy_conf = {'name': f'decoy',
                  'group': 'event_server',
                  'monitor_address': monitor_server,
                  'component_address': decoy_address}

    await async_group.spawn(hat.monitor.client.run_component, decoy_conf,
                            run_decoy_cb)

    event_server_factory()

    assert (await client_future) == 'test'


@pytest.mark.asyncio
async def test_run_client_register_on_cancel(event_server_factory,
                                             client_factory,
                                             short_client_reconnect_delay):
    register_events = [hat.event.common.RegisterEvent(
        event_type=['test'],
        source_timestamp=None,
        payload=None)]
    is_running = asyncio.Event()
    events_queue = aio.Queue()

    async def run_cb(event_client):
        try:
            is_running.set()
            while True:
                await asyncio.sleep(1)
        finally:
            events = await event_client.register_with_response(register_events)
            events_queue.put_nowait(events)

    event_server_factory()
    client_group, _ = client_factory(run_cb)
    await is_running.wait()
    await client_group.async_close()

    events = await events_queue.get()
    assert all(common.compare_register_event_vs_event(r, e)
               for r, e in zip(register_events, events))
