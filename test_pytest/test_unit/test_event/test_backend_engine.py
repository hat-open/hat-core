import contextlib
import itertools
import sys
import types

import pytest

from hat import aio
from hat.event.server import common
import hat.event.server.backend_engine


pytestmark = pytest.mark.asyncio


@pytest.fixture
def backend_module_name():
    for i in itertools.count(1):
        name = f'mock_backend_module_{i}'
        if name not in sys.modules:
            return name


@pytest.fixture
def create_backend_module(backend_module_name):

    @contextlib.contextmanager
    def create_backend_module(get_last_event_id_cb=None,
                              register_cb=None, query_cb=None):

        instances = []

        async def create(conf):
            backend = Backend(conf)
            instances.append(backend)
            return backend

        class Backend(common.Backend):

            def __init__(self, conf):
                self._conf = conf
                self._async_group = aio.Group()

            @property
            def conf(self):
                return self._conf

            @property
            def async_group(self):
                return self._async_group

            async def get_last_event_id(self, server_id):
                if not get_last_event_id_cb:
                    return 0
                return get_last_event_id_cb(server_id)

            async def register(self, events):
                if not register_cb:
                    return events
                return register_cb(events)

            async def query(self, data):
                if not query_cb:
                    return []
                return query_cb(data)

        module = types.ModuleType(backend_module_name)
        module.json_schema_id = None
        module.json_schema_repo = None
        module.create = create
        sys.modules[backend_module_name] = module
        try:
            yield instances
        finally:
            del sys.modules[backend_module_name]

    return create_backend_module


async def test_create(backend_module_name, create_backend_module):
    conf = {'server_id': 123,
            'backend': {'module': backend_module_name,
                        'data': 321}}

    with pytest.raises(Exception):
        await hat.event.server.backend_engine(conf)

    with create_backend_module() as backends:
        assert len(backends) == 0

        engine = await hat.event.server.backend_engine.create(conf)

        assert engine.is_open
        assert len(backends) == 1
        assert backends[0].conf == conf['backend']
        assert backends[0].is_open

        await engine.async_close()
        assert backends[0].is_closed


async def test_get_last_event_id(backend_module_name, create_backend_module):
    conf = {'server_id': 123,
            'backend': {'module': backend_module_name}}
    event_id = common.EventId(conf['server_id'], 321)

    def get_last(server_id):
        assert server_id == conf['server_id']
        return event_id

    with create_backend_module(get_last_event_id_cb=get_last):
        engine = await hat.event.server.backend_engine.create(conf)

        result = await engine.get_last_event_id()
        assert result == event_id

        await engine.async_close()


async def test_register(backend_module_name, create_backend_module):
    conf = {'server_id': 123,
            'backend': {'module': backend_module_name}}
    event_ids = [common.EventId(conf['server_id'], i) for i in range(10)]
    process_events = [
        common.ProcessEvent(event_id=event_id,
                            source=common.Source(common.SourceType.MODULE,
                                                 'abc', 1),
                            event_type=[],
                            source_timestamp=common.now(),
                            payload=None)
        for event_id in event_ids]

    def register(events):
        return events

    with create_backend_module(register_cb=register):
        engine = await hat.event.server.backend_engine.create(conf)

        events = await engine.register(process_events)
        assert [i.event_id for i in events] == event_ids

        await engine.async_close()


async def test_query(backend_module_name, create_backend_module):
    conf = {'server_id': 123,
            'backend': {'module': backend_module_name}}
    event_ids = [common.EventId(conf['server_id'], i) for i in range(10)]
    events = [common.Event(event_id=event_id,
                           event_type=[],
                           timestamp=common.now(),
                           source_timestamp=None,
                           payload=None)
              for event_id in event_ids]
    query_data = common.QueryData()

    def query(data):
        assert query_data == data
        return events

    with create_backend_module(query_cb=query):
        engine = await hat.event.server.backend_engine.create(conf)

        result = await engine.query(query_data)
        assert result == events

        await engine.async_close()
