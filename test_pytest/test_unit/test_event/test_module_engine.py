import asyncio
import functools
import itertools
import sys
import types

import pytest

from hat import aio
from hat.event.server import common
import hat.event.client
import hat.event.server.module_engine


pytestmark = pytest.mark.asyncio


@pytest.fixture
def create_module():
    module_names = []

    def create_module(process_cb):

        async def create(conf, engine):
            module = Module()
            module._async_group = aio.Group()
            module._subscription = common.Subscription([['*']])
            return module

        class Module(common.Module):

            @property
            def async_group(self):
                return self._async_group

            @property
            def subscription(self):
                return self._subscription

            async def create_session(self):
                session = Session()
                session._async_group = self._async_group.create_subgroup()
                return session

        class Session(common.ModuleSession):

            @property
            def async_group(self):
                return self._async_group

            async def process(self, events):
                return await aio.call(process_cb, events)

        for i in itertools.count(1):
            module_name = f'mock_module_{i}'
            if module_name not in sys.modules:
                break

        module = types.ModuleType(module_name)
        module.json_schema_id = None
        module.json_schema_repo = None
        module.create = create
        sys.modules[module_name] = module

        module_names.append(module_name)
        return module_name

    try:
        yield create_module
    finally:
        for module_name in module_names:
            del sys.modules[module_name]


class BackendEngine(aio.Resource):

    def __init__(self, register_cb=None, query_cb=None, server_id=0):
        self._register_cb = register_cb
        self._query_cb = query_cb
        self._server_id = server_id
        self._async_group = aio.Group()

    @property
    def async_group(self):
        return self._async_group

    async def get_last_event_id(self):
        return common.EventId(self._server_id, 0)

    async def register(self, process_events):
        if not self._register_cb:
            now = common.now()
            return [
                common.Event(event_id=process_event.event_id,
                             event_type=process_event.event_type,
                             timestamp=now,
                             source_timestamp=process_event.source_timestamp,
                             payload=process_event.payload)
                for process_event in process_events]
        return self._register_cb(process_events)

    async def query(self, data):
        if not self._query_cb:
            return []
        return self._query_cb(data)


async def test_create_empty():
    conf = {'modules': []}
    backend = BackendEngine()

    engine = await hat.event.server.module_engine.create(conf, backend)
    assert engine.is_open

    await engine.async_close()
    assert engine.is_closed

    await backend.async_close()


async def test_create_process_event():
    server_id = 123
    source = common.Source(common.SourceType.MODULE, None, 321)
    register_events = [common.RegisterEvent(event_type=(str(i),),
                                            source_timestamp=common.now(),
                                            payload=None)
                       for i in range(10)]

    conf = {'modules': []}
    backend = BackendEngine(server_id=server_id)
    engine = await hat.event.server.module_engine.create(conf, backend)

    event_ids = set()
    for register_event in register_events:
        process_event = engine.create_process_event(source, register_event)
        assert process_event.event_type == register_event.event_type
        assert (process_event.source_timestamp ==
                register_event.source_timestamp)
        assert process_event.payload == register_event.payload
        assert process_event.source == source
        assert process_event.event_id.server == 123
        assert process_event.event_id not in event_ids
        event_ids.add(process_event.event_id)

    await engine.async_close()
    await backend.async_close()


@pytest.mark.parametrize("module_count", [0, 1, 2, 5])
@pytest.mark.parametrize("value", [0, 1, 2, 5])
async def test_register(create_module, module_count, value):

    backend_events = asyncio.Future()
    engine_events = asyncio.Future()

    def on_backend_events(events):
        backend_events.set_result(events)
        return events

    def on_engine_events(events):
        engine_events.set_result(events)

    def process(source, events):
        for event in events:
            if event.source.type == common.SourceType.MODULE:
                if event.source != source:
                    continue
            if not event.payload.data:
                continue
            yield engine.create_process_event(source, common.RegisterEvent(
                event_type=event.event_type,
                source_timestamp=None,
                payload=event.payload._replace(data=event.payload.data - 1)))

    def get_values(events):
        return [event.payload.data for event in events]

    sources = [common.Source(common.SourceType.MODULE, None, i)
               for i in range(module_count)]
    module_names = [create_module(functools.partial(process, source))
                    for source in sources]

    conf = {'modules': [{'module': module_name}
                        for module_name in module_names]}
    backend = BackendEngine(register_cb=on_backend_events)

    engine = await hat.event.server.module_engine.create(conf, backend)
    engine.register_events_cb(on_engine_events)

    source = common.Source(common.SourceType.COMMUNICATION, None, 0)
    result = await engine.register(source, [common.RegisterEvent(
        event_type=(),
        source_timestamp=None,
        payload=common.EventPayload(common.EventPayloadType.JSON,  value))])
    backend_events = backend_events.result()
    engine_events = engine_events.result()

    values = [value]
    if module_count:
        while (last := values[-1]):
            values.extend([last - 1] * module_count)

    assert get_values(result) == [value]
    assert get_values(backend_events) == values
    assert get_values(engine_events) == values

    await engine.async_close()
    await backend.async_close()


async def test_query():
    query_data = common.QueryData()
    events = [common.Event(event_id=common.EventId(1, i),
                           event_type=(),
                           timestamp=common.now(),
                           source_timestamp=None,
                           payload=None)
              for i in range(10)]

    def on_query(data):
        assert data == query_data
        return events

    conf = {'modules': []}
    backend = BackendEngine(query_cb=on_query)
    engine = await hat.event.server.module_engine.create(conf, backend)

    result = await engine.query(query_data)
    assert result == events

    await engine.async_close()
    await backend.async_close()


async def test_cancel_register(create_module):

    process_enter_future = asyncio.Future()
    process_exit_future = asyncio.Future()

    async def process(events):
        process_enter_future.set_result(None)
        await process_exit_future
        return []

    source = common.Source(common.SourceType.MODULE, None, 1)
    module_name = create_module(process)

    conf = {'modules': [{'module': module_name}]}
    backend = BackendEngine()

    engine = await hat.event.server.module_engine.create(conf, backend)
    registered_events = aio.Queue()
    engine.register_events_cb(registered_events.put_nowait)

    source = common.Source(common.SourceType.COMMUNICATION, None, 0)
    register_future = asyncio.ensure_future(
        engine.register(source, [common.RegisterEvent(
            event_type=(),
            source_timestamp=None,
            payload=None)]))

    await process_enter_future
    register_future.cancel()
    process_exit_future.set_result(None)

    assert registered_events.empty()
    await asyncio.wait_for(registered_events.get(), 0.01)

    assert engine.is_open

    await engine.async_close()
