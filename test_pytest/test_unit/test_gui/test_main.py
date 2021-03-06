import asyncio
import contextlib
import pytest

from hat import aio
from hat import util
import hat.event.client
import hat.event.common
import hat.event.server.main
import hat.gui.main
import hat.gui.server
import hat.gui.view

import test_unit.test_gui.mock


@pytest.fixture
def event_server_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
async def event_server(event_server_port):
    conf = {
        'backend_engine': {
            'server_id': 1,
            'backend': {
                'module': 'hat.event.server.backends.memory'}},
        'module_engine': {'modules': []},
        'communication': {
            'address': f'tcp+sbs://127.0.0.1:{event_server_port}'}}
    async with aio.Group() as group:
        group.spawn(hat.event.server.main.run, conf, None)
        await asyncio.sleep(0.01)  # Wait for event server to start
        yield


@pytest.fixture
async def event_client_factory(event_server, event_server_port):
    clients = []

    async def factory(subscriptions=None):
        address = f'tcp+sbs://127.0.0.1:{event_server_port}'
        client = await hat.event.client.connect(address, subscriptions)
        clients.append(client)
        return client

    yield factory

    for client in clients:
        await client.async_close()


class _Closeable(aio.Resource):

    def __init__(self):
        self._async_group = aio.Group()

    @property
    def async_group(self):
        return self._async_group


@pytest.fixture
async def adapter_factory(monkeypatch, event_client_factory):

    all_adapters = []

    @contextlib.asynccontextmanager
    async def factory(conf_adapters):
        conf = {'adapters': conf_adapters,
                'views': None,
                'server': None}
        adapters = {}
        create_default = test_unit.test_gui.mock.create

        async def create_view_manager(conf):
            return _Closeable()

        async def create_server(conf, ui_path, adapters, views):
            return _Closeable()

        async def create_patch(conf, client):
            adapter = await create_default(conf, client)
            adapters[conf['name']] = adapter
            all_adapters.append(adapter)
            return adapter

        with monkeypatch.context() as ctx:
            ctx.setattr(hat.gui.view, 'create_view_manager',
                        create_view_manager)
            ctx.setattr(hat.gui.server, 'create', create_server)
            ctx.setattr(test_unit.test_gui.mock, 'create', create_patch)
            async with aio.Group() as group:
                group.spawn(
                    hat.gui.main.run_with_event, conf, None,
                    await event_client_factory(
                        [test_unit.test_gui.mock.event_type_prefix + ['*']]))
                await asyncio.sleep(0.1)
                yield adapters

    yield factory
    for adapter in all_adapters:
        await adapter.async_close()


@pytest.mark.asyncio
async def test_event_receive(event_client_factory, adapter_factory):
    client = await event_client_factory([['hat', '*'],
                                         ['should', '*']])
    adapters_conf = [{'name': 'adapter1',
                      'module': 'test_unit.test_gui.mock'}]
    async with adapter_factory(adapters_conf) as adapters:
        adapter = adapters['adapter1']
        assert adapter.conf == adapters_conf[0]

        client.register([
            hat.event.common.RegisterEvent(
                event_type=['hat', 'gui', 'mock', 'system'],
                source_timestamp=hat.event.common.now(),
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'})),
            hat.event.common.RegisterEvent(
                event_type=['hat', 'gui', 'mock'],
                source_timestamp=None,
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'})),
            hat.event.common.RegisterEvent(
                event_type=['should', 'not', 'receive'],
                source_timestamp=None,
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'}))])
        events = await client.receive()
        filtered = [ev for ev in events
                    if ev.event_type != ['should', 'not', 'receive']]
        adapter_events = await adapter.client.receive()
        assert filtered == adapter_events


@pytest.mark.asyncio
async def test_event_register(event_client_factory, adapter_factory):
    client = await event_client_factory([['hat', '*'],
                                         ['should', '*']])
    adapters_conf = [{'name': 'adapter1',
                      'module': 'test_unit.test_gui.mock'}]
    async with adapter_factory(adapters_conf) as adapters:
        adapter = adapters['adapter1']

        register_events = [
            hat.event.common.RegisterEvent(
                event_type=['hat', 'gui', 'mock', 'system'],
                source_timestamp=hat.event.common.now(),
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'})),
            hat.event.common.RegisterEvent(
                event_type=['hat', 'gui', 'mock'],
                source_timestamp=None,
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'})),
            hat.event.common.RegisterEvent(
                event_type=['should', 'register'],
                source_timestamp=None,
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'}))]
        adapter.client.register(register_events)
        events = await client.receive()
        assert len(register_events) == len(events)
        for ev in events:
            assert util.first(register_events, lambda reg_ev: (
                ev.event_type == reg_ev.event_type
                and ev.source_timestamp == reg_ev.source_timestamp
                and ev.payload == reg_ev.payload))


@pytest.mark.asyncio
async def test_event_register_with_response(event_client_factory,
                                            adapter_factory):
    client = await event_client_factory([['hat', '*'],
                                         ['1', '2']])
    adapters_conf = [{'name': 'adapter1',
                      'module': 'test_unit.test_gui.mock'}]
    async with adapter_factory(adapters_conf) as adapters:
        adapter = adapters['adapter1']

        register_events = [
            hat.event.common.RegisterEvent(
                event_type=['hat', 'gui', 'mock', 'system'],
                source_timestamp=hat.event.common.now(),
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'})),
            hat.event.common.RegisterEvent(
                event_type=['hat', 'gui', 'mock'],
                source_timestamp=None,
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'})),
            hat.event.common.RegisterEvent(
                event_type=['1', '2'],
                source_timestamp=None,
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'}))]
        response = await adapter.client.register_with_response(register_events)
        events = await client.receive()
        assert response == events


@pytest.mark.asyncio
async def test_event_query(event_client_factory, adapter_factory):
    client = await event_client_factory([['hat', '*'],
                                         ['1', '2']])
    adapters_conf = [{'name': 'adapter1',
                      'module': 'test_unit.test_gui.mock'}]
    async with adapter_factory(adapters_conf) as adapters:
        adapter = adapters['adapter1']

        register_events = [
            hat.event.common.RegisterEvent(
                event_type=['hat', 'gui', 'mock', 'system'],
                source_timestamp=hat.event.common.now(),
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'})),
            hat.event.common.RegisterEvent(
                event_type=['hat', 'gui', 'mock'],
                source_timestamp=None,
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'})),
            hat.event.common.RegisterEvent(
                event_type=['1', '2'],
                source_timestamp=None,
                payload=hat.event.common.EventPayload(
                    hat.event.common.EventPayloadType.JSON,
                    data={'abc': 'def'}))]
        await client.register_with_response(register_events)
        events = await adapter.client.query(
            hat.event.common.QueryData(event_types=[['1', '2']]))
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ['1', '2']
        assert event.source_timestamp is None
        assert event.payload.type == hat.event.common.EventPayloadType.JSON
        assert event.payload.data == {'abc': 'def'}


@pytest.mark.asyncio
async def test_adapter_close(adapter_factory):
    adapters_conf = [{'name': 'adapter1',
                      'module': 'test_unit.test_gui.mock'}]
    async with adapter_factory(adapters_conf) as adapters:
        pass
    async_group = aio.Group()
    for adapter in adapters.values():
        async_group.spawn(adapter.wait_closed)
    await async_group.async_close(cancel=False)
