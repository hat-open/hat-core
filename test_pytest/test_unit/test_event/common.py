import contextlib
import unittest.mock

import hat.event.common
import hat.event.server.common
import hat.event.server.module_engine
import hat.event.server.backend_engine

from hat import util
from hat.util import aio


def create_module_engine(register_cb=lambda _: [], query_cb=lambda _: []):
    engine = MockModuleEngine()
    engine._async_group = aio.Group()
    engine._last_instance_id = 0
    engine._register_cb = register_cb
    engine._query_cb = query_cb
    engine._register_event_cbs = util.CallbackRegistry()
    return engine


class MockModuleEngine(hat.event.server.module_engine.ModuleEngine):

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self):
        await self._async_group.async_close()

    def register_events_cb(self, cb):
        return self._register_event_cbs.register(cb)

    def create_process_event(self, source, event):
        instance_id = self._last_instance_id
        self._last_instance_id += 1
        return hat.event.server.common.ProcessEvent(
            event_id=hat.event.common.EventId(server=0, instance=instance_id),
            source=source,
            event_type=event.event_type,
            source_timestamp=event.source_timestamp,
            payload=event.payload)

    async def register(self, source, events):
        events = [self.create_process_event(source, event) for event in events]
        registered_events = await aio.call(self._register_cb, events)
        self._register_event_cbs.notify(registered_events)
        return registered_events

    async def query(self, data):
        return await aio.call(self._query_cb, data)


def create_backend_engine(register_cb=lambda _: [], query_cb=lambda _: []):
    engine = MockBackendEngine()
    engine._async_group = aio.Group()
    engine._register_cb = register_cb
    engine._query_cb = query_cb
    engine._server_id = 0
    return engine


class MockBackendEngine(hat.event.server.backend_engine.BackendEngine):

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self):
        await self._async_group.async_close()

    async def get_last_event_id(self):
        return hat.event.common.EventId(server=0, instance=0)

    async def register(self, events):
        return await aio.call(self._register_cb, events)

    async def query(self, data):
        return await aio.call(self._query_cb, data)


@contextlib.contextmanager
def get_return_values(f):
    values = []

    async def wrapper(*args, **kwargs):
        value = await f(*args, **kwargs)
        values.append(value)
        return value

    with unittest.mock.patch(f'{f.__module__}.{f.__name__}', new=wrapper):
        yield values


def process_event_to_event(event,
                           timestamp=hat.event.common.Timestamp(s=0, us=0)):
    return hat.event.common.Event(
        event_id=event.event_id,
        event_type=event.event_type,
        timestamp=timestamp,
        source_timestamp=event.source_timestamp,
        payload=event.payload)


def compare_register_event_vs_event(e1, e2):
    return (e1.event_type == e2.event_type and
            e1.source_timestamp == e2.source_timestamp and
            e1.payload == e2.payload)


def compare_proces_event_vs_event(e1, e2):
    return (e1.event_type == e2.event_type and
            e1.source_timestamp == e2.source_timestamp and
            e1.payload == e2.payload and
            e1.event_id == e2.event_id)


def compare_events(e1, e2):
    return e1 == e2
