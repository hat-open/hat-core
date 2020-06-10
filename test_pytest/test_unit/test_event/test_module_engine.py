import pytest
import asyncio
import functools
import itertools
import contextlib
import sys
import types

from hat import util
from hat.util import aio
import hat.event.server.module_engine
import hat.event.server.common
import hat.event.common

from test_unit.test_event import common
import test_unit.test_event.modules.module1
import test_unit.test_event.modules.module2
import test_unit.test_event.modules.transparent
import test_unit.test_event.modules.event_killer


@pytest.fixture
def module_engine_conf():
    return {'modules': []}


@pytest.fixture
def source_comm():
    return hat.event.server.common.Source(
        type=hat.event.server.common.SourceType.COMMUNICATION,
        name=None,
        id=0)


@pytest.fixture
def register_events():
    event_types = [['a'],
                   ['a'],
                   ['b'],
                   ['a', 'b'],
                   ['a', 'b', 'c'],
                   []]
    return [hat.event.common.RegisterEvent(event_type=et,
                                           source_timestamp=None,
                                           payload=None)
            for et in event_types]


@pytest.fixture
def create_module():

    @contextlib.contextmanager
    def create_module(name, subscriptions=[['*']], process_cb=None):

        if not process_cb:
            empty_changes = hat.event.server.common.SessionChanges([], [])
            process_cb = lambda _: empty_changes  # NOQA

        async def create(conf, module_engine):
            return Module()

        class Module(hat.event.server.common.Module):

            def __init__(self):
                self._closed = asyncio.Future()

            @property
            def subscriptions(self):
                return subscriptions

            @property
            def closed(self):
                return asyncio.shield(self._closed)

            async def async_close(self):
                self._closed.set_result(True)

            async def create_session(self):
                return Session()

        class Session(hat.event.server.common.ModuleSession):

            def __init__(self):
                self._closed = asyncio.Future()

            @property
            def closed(self):
                return asyncio.shield(self._closed)

            async def async_close(self, events):
                self._closed.set_result(True)

            async def process(self, changes):
                return await aio.call(process_cb, changes)

        module = types.ModuleType(name)
        module.json_schema_id = None
        module.create = create
        sys.modules[name] = module
        try:
            yield
        finally:
            del sys.modules[name]

    return create_module


def assert_notified_changes(sessions, registered_events):
    for session in sessions:
        changes_notified_new_exp = filter_events_by_subscriptions(
            registered_events +
            [i for ss in sessions for i in ss.changes_result_new
             if ss is not session],
            session._module.subscriptions)
        changes_notified_deleted_exp = filter_events_by_subscriptions(
            [i for ss in sessions for i in ss.changes_result_deleted
             if ss is not session],
            session._module.subscriptions)
        assert (sorted(session.changes_notified_new,
                       key=lambda i: i.event_id) ==
                sorted(changes_notified_new_exp, key=lambda i: i.event_id))
        assert (sorted(session.changes_notified_deleted,
                       key=lambda i: i.event_id) ==
                sorted(changes_notified_deleted_exp, key=lambda i: i.event_id))


def assert_events_vs_changes_result(sessions, registered_events, events):
    events_exp = list(registered_events)
    for session in sessions:
        events_exp += session.changes_result_new
    for session in sessions:
        for e in session.changes_result_deleted:
            if e not in events_exp:
                continue
            events_exp.remove(e)
    assert len(events) == len(events_exp)
    event_ids_exp = {e.event_id: e for e in events_exp}
    assert all(e.event_id in event_ids_exp for e in events)
    assert all(common.compare_proces_event_vs_event(event_ids_exp[e.event_id],
                                                    e)
               for e in events)


async def assert_closure(backend_engine, module_engine, modules):
    await backend_engine.async_close()
    await module_engine.async_close()
    assert module_engine.closed.done()
    await asyncio.gather(*(module.closed for module in modules))
    assert all(module.session_queue.empty() for module in modules)


def filter_events_by_subscriptions(events, subscriptions):
    ret = []
    for event in events:
        if util.first(subscriptions,
                      lambda q_type: hat.event.common.matches_query_type(
                          event.event_type, q_type)) is not None:
            ret.append(event)
    return ret


@pytest.mark.asyncio
async def test_create_process_event(module_engine_conf, register_events,
                                    source_comm):
    backend_engine = common.create_backend_engine()
    module_engine = await hat.event.server.module_engine.create(
        module_engine_conf, backend_engine)

    process_events = [module_engine.create_process_event(source_comm, e)
                      for e in register_events]
    assert all(type(e) == hat.event.server.common.ProcessEvent
               for e in process_events)
    assert all(common.compare_register_event_vs_event(e1, e2)
               for e1, e2 in zip(register_events, process_events))
    assert all(e.source == source_comm for e in process_events)
    unique_ids = set(e.event_id for e in process_events)
    assert len(process_events) == len(unique_ids)
    assert all(e.event_id.server == backend_engine._server_id
               for e in process_events)
    # repeating with same register events results with new process events
    process_events2 = [module_engine.create_process_event(source_comm, e)
                       for e in register_events]
    unique_ids = set(e.event_id for e in itertools.chain(process_events,
                                                         process_events2))
    assert (len(process_events + process_events2) == len(unique_ids))

    await backend_engine.async_close()
    await module_engine.async_close()


@pytest.mark.asyncio
async def test_register(module_engine_conf, register_events, source_comm):

    def register_cb(events):
        return [common.process_event_to_event(i) for i in events]

    event_queue = aio.Queue()
    backend_engine = common.create_backend_engine(register_cb=register_cb)
    module_engine = await hat.event.server.module_engine.create(
        module_engine_conf, backend_engine)
    module_engine.register_events_cb(
        lambda events: event_queue.put_nowait(events))

    process_events = [module_engine.create_process_event(source_comm, i)
                      for i in register_events]
    events = await module_engine.register(process_events)
    events_notified = await event_queue.get()

    assert all(common.compare_proces_event_vs_event(e1, e2)
               for e1, e2 in zip(process_events, events))
    assert all(common.compare_events(e1, e2)
               for e1, e2 in zip(events, events_notified))

    await backend_engine.async_close()
    await module_engine.async_close()
    assert module_engine.closed.done()
    assert event_queue.empty()


@pytest.mark.asyncio
async def test_query(module_engine_conf, register_events):

    def query_cb(events):
        return mock_result

    mock_query = hat.event.common.QueryData()
    mock_result = [hat.event.common.Event(
        event_id=hat.event.common.EventId(server=0, instance=0),
        event_type=['mock'],
        timestamp=hat.event.common.Timestamp(s=0, us=0),
        source_timestamp=None,
        payload=None)]

    backend_engine = common.create_backend_engine(query_cb=query_cb)
    module_engine = await hat.event.server.module_engine.create(
        module_engine_conf, backend_engine)

    query_resp = await module_engine.query(mock_query)

    assert query_resp == mock_result

    await backend_engine.async_close()
    await module_engine.async_close()
    assert module_engine.closed.done()


@pytest.mark.asyncio
async def test_register_query_on_close(module_engine_conf, register_events,
                                       source_comm):
    comm_register = asyncio.Event()

    async def unresponsive_cb(async_event, _):
        async_event.set()
        while True:
            await asyncio.sleep(1)

    backend_engine = common.create_backend_engine(
        register_cb=functools.partial(unresponsive_cb, comm_register))
    module_engine = await hat.event.server.module_engine.create(
        module_engine_conf, backend_engine)
    assert not module_engine.closed.done()

    process_events = [module_engine.create_process_event(source_comm, i)
                      for i in register_events]
    async with aio.Group() as group:
        register_future = group.spawn(module_engine.register, process_events)

        await comm_register.wait()

        await backend_engine.async_close()
        await module_engine.async_close()
        assert module_engine.closed.done()

        with pytest.raises(asyncio.CancelledError):
            await register_future

    with pytest.raises(hat.event.server.module_engine.ModuleEngineClosedError):
        await module_engine.register(process_events)
    with pytest.raises(hat.event.server.module_engine.ModuleEngineClosedError):
        await module_engine.query(hat.event.common.QueryData())


@pytest.mark.asyncio
async def test_module1(module_engine_conf, register_events, source_comm,
                       monkeypatch):

    def register_cb(events):
        return [common.process_event_to_event(i) for i in events]

    backend_engine = common.create_backend_engine(register_cb=register_cb)
    module_engine_conf['modules'] = [{
        'module': 'test_unit.test_event.modules.module1'}]
    with common.get_return_values(
            test_unit.test_event.modules.module1.create) as modules:
        module_engine = await hat.event.server.module_engine.create(
            module_engine_conf, backend_engine)
    module = modules[0]

    assert len(modules) == 1
    assert not module.closed.done()

    event_queue = aio.Queue()
    module_engine.register_events_cb(
        lambda events: event_queue.put_nowait(events))
    process_events = [module_engine.create_process_event(source_comm, i)
                      for i in register_events]
    events_on_register = await module_engine.register(process_events)
    session = await module.session_queue.get()
    await session.closed
    filtered_events = filter_events_by_subscriptions(
        process_events, module.subscriptions)
    assert session.changes_notified_new == filtered_events

    events = await event_queue.get()

    assert events == events_on_register
    assert_events_vs_changes_result([session], process_events, events)
    assert len(events) == len(process_events)
    assert session.events_on_close == events

    await assert_closure(backend_engine, module_engine, modules)


@pytest.mark.asyncio
async def test_modules(module_engine_conf, register_events, source_comm):

    def register_cb(events):
        return [common.process_event_to_event(i) for i in events]

    backend_engine = common.create_backend_engine(register_cb=register_cb)
    module_engine_conf['modules'] = [
        {'module': 'test_unit.test_event.modules.module2'},
        {'module': 'test_unit.test_event.modules.module1'},
        {'module': 'test_unit.test_event.modules.transparent'}]
    with contextlib.ExitStack() as stack:
        modules = [stack.enter_context(common.get_return_values(m))
                   for m in [
                       test_unit.test_event.modules.module1.create,
                       test_unit.test_event.modules.module2.create,
                       test_unit.test_event.modules.transparent.create]]
        module_engine = await hat.event.server.module_engine.create(
            module_engine_conf, backend_engine)

    modules = [m for ms in modules for m in ms]

    assert len(modules) == 3
    assert all(not module.closed.done() for module in modules)

    event_queue = aio.Queue()
    module_engine.register_events_cb(
        lambda events: event_queue.put_nowait(events))

    process_events = [module_engine.create_process_event(source_comm, i)
                      for i in register_events]
    events_on_register = await module_engine.register(process_events)
    sessions = [await module.session_queue.get() for module in modules]
    await asyncio.gather(*(session.closed for session in sessions))

    assert_notified_changes(sessions, process_events)

    events = await event_queue.get()

    assert events == events_on_register
    assert_events_vs_changes_result(sessions, process_events, events)
    assert all(session.events_on_close == events for session in sessions)

    await assert_closure(backend_engine, module_engine, modules)


@pytest.mark.asyncio
async def test_module_event_killer(module_engine_conf, register_events,
                                   source_comm):

    def register_cb(events):
        return [common.process_event_to_event(i) for i in events]

    backend_engine = common.create_backend_engine(register_cb=register_cb)
    module_engine_conf['modules'] = [
        {'module': 'test_unit.test_event.modules.module1'},
        {'module': 'test_unit.test_event.modules.module2'},
        {'module': 'test_unit.test_event.modules.event_killer'}]
    with contextlib.ExitStack() as stack:
        modules = [stack.enter_context(common.get_return_values(m))
                   for m in [
                       test_unit.test_event.modules.module1.create,
                       test_unit.test_event.modules.module2.create,
                       test_unit.test_event.modules.event_killer.create]]
        module_engine = await hat.event.server.module_engine.create(
            module_engine_conf, backend_engine)
    modules = [m for ms in modules for m in ms]

    process_events = [module_engine.create_process_event(source_comm, i)
                      for i in register_events]
    events = await module_engine.register(process_events)
    sessions = [await module.session_queue.get() for module in modules]

    assert not events
    assert_events_vs_changes_result(sessions, process_events, events)
    assert all(session.events_on_close == events for session in sessions)

    await assert_closure(backend_engine, module_engine, modules)


@pytest.mark.asyncio
async def test_sessions(module_engine_conf, register_events, source_comm):

    def register_cb(events):
        return [common.process_event_to_event(
            i,
            hat.event.common.now()) for i in events]

    backend_engine = common.create_backend_engine(register_cb=register_cb)
    module_engine_conf['modules'] = [
        {'module': 'test_unit.test_event.modules.module2'},
        {'module': 'test_unit.test_event.modules.module1'}]
    with contextlib.ExitStack() as stack:
        modules = [stack.enter_context(common.get_return_values(m))
                   for m in [
                       test_unit.test_event.modules.module1.create,
                       test_unit.test_event.modules.module2.create]]
        module_engine = await hat.event.server.module_engine.create(
            module_engine_conf, backend_engine)

    modules = [m for ms in modules for m in ms]

    process_events = [module_engine.create_process_event(source_comm, i)
                      for i in register_events]
    await module_engine.register(process_events)
    sessions1 = [await module.session_queue.get() for module in modules]
    await asyncio.gather(*(session.closed for session in sessions1))
    assert all(module.session_queue.empty() for module in modules)

    process_events = [module_engine.create_process_event(source_comm, i)
                      for i in register_events]
    await module_engine.register(process_events)
    sessions2 = [await module.session_queue.get() for module in modules]
    await asyncio.gather(*(session.closed for session in sessions2))
    assert all(module.session_queue.empty() for module in modules)

    assert all(s not in sessions1 for s in sessions2)

    await assert_closure(backend_engine, module_engine, modules)


@pytest.mark.asyncio
async def test_empty_changes(create_module):
    module_name = 'TestEmptyChanges'
    source = hat.event.server.common.Source(
        type=hat.event.server.common.SourceType.COMMUNICATION,
        name=None,
        id=1)
    changes = []

    def process(c):
        changes.append(c)
        return hat.event.server.common.SessionChanges([], [])

    with create_module(module_name,
                       subscriptions=[['a', '*']],
                       process_cb=process):
        module_engine_conf = {'modules': [{'module': module_name}]}
        backend_engine = common.create_backend_engine()
        module_engine = await hat.event.server.module_engine.create(
                module_engine_conf, backend_engine)

        assert changes == []

        await module_engine.register([])
        assert changes == []

        await module_engine.register([
            module_engine.create_process_event(
                source, hat.event.common.RegisterEvent(
                    event_type=['b', 'c'],
                    source_timestamp=None,
                    payload=None))
        ])
        assert changes == []

        await module_engine.register([
            module_engine.create_process_event(
                source, hat.event.common.RegisterEvent(
                    event_type=['a', 'c'],
                    source_timestamp=None,
                    payload=None))
        ])
        assert len(changes) == 1

        await module_engine.async_close()
        await backend_engine.async_close()
