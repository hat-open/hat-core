import asyncio

import pytest

from hat import aio
from hat import util
from hat.event.server import common
import hat.event.client
import hat.event.server.communication


pytestmark = pytest.mark.asyncio


@pytest.fixture
def comm_port():
    return util.get_unused_tcp_port()


@pytest.fixture
def comm_address(comm_port):
    return f'tcp+sbs://127.0.0.1:{comm_port}'


@pytest.fixture
def comm_conf(comm_address):
    return {'address': comm_address}


class ModuleEngine(aio.Resource):

    def __init__(self, register_cb=None, query_cb=None, server_id=1):
        self._register_cb = register_cb
        self._query_cb = query_cb
        self._server_id = server_id
        self._last_instance_id = 0
        self._async_group = aio.Group()
        self._events_cbs = util.CallbackRegistry()

    @property
    def async_group(self):
        return self._async_group

    def register_events_cb(self, cb):
        return self._events_cbs.register(cb)

    def create_process_event(self, source, event):
        self._last_instance_id += 1
        return common.ProcessEvent(
            event_id=common.EventId(
                server=self._server_id,
                instance=self._last_instance_id),
            source=source,
            event_type=event.event_type,
            source_timestamp=event.source_timestamp,
            payload=event.payload)

    async def register(self, source, events):
        if not self._register_cb:
            return [None for _ in events]
        return self._register_cb(source, events)

    async def query(self, data):
        if not self._query_cb:
            return []
        return self._query_cb(data)

    def notify(self, events):
        self._events_cbs.notify(events)


@pytest.mark.parametrize("client_count", [1, 2, 5])
async def test_client_connect_disconnect(comm_address, comm_conf,
                                         client_count):

    with pytest.raises(Exception):
        await hat.event.client.connect(comm_address)

    engine = ModuleEngine()
    comm = await hat.event.server.communication.create(comm_conf, engine)

    clients = []
    for _ in range(client_count):
        client = await hat.event.client.connect(comm_address)
        clients.append(client)

    assert not comm.is_closed
    for client in clients:
        assert not client.is_closed

    await comm.async_close()
    await engine.async_close()
    for client in clients:
        await client.wait_closed()

    with pytest.raises(Exception):
        await hat.event.client.connect(comm_address)


@pytest.mark.parametrize("subscriptions", [
    [()],
    [('*',)],
    [('?',)],
    [('?', '*')],
    [('?', '?')],
    [('?', '?', '*')],
    [('?', '?', '?')],
    [('?', '?', '?', '*')],
    [('a',)],
    [('a', '*')],
    [('a', '?')],
    [('a', '?', '*')],
    [('a', '?', '?')],
    [('a', 'b')],
    [('a', 'b', '*')],
    [('a', 'b', '?')],
    [('?', 'b')],
    [('?', 'b', '?')],
    [('?', 'b', '*')],
    [('a', 'b', 'c')],
    [('a',), ()],
    [('a',), ('*',)],
    [('a',), ('?',)],
    [('a',), ('b',)],
    [('a',), ('a', 'a')],
    [('a',), ('a', 'b')],
    [('b',), ('a', 'b')],
    [('a',), ('a', 'b'), ('a', 'b', 'c')],
    [('', '', '')],
    [('x', 'y', 'z')]
])
async def test_subscribe(comm_address, comm_conf, subscriptions):
    subscription = common.Subscription(subscriptions)
    event_types = [[],
                   ['a'],
                   ['b'],
                   ['a', 'a'],
                   ['a', 'b'],
                   ['a', 'b', 'c'],
                   ['', '', '']]
    filtered_event_types = [event_type for event_type in event_types
                            if subscription.matches(event_type)]
    events = [
        hat.event.common.Event(
            event_id=hat.event.common.EventId(server=0, instance=i),
            event_type=event_type,
            timestamp=common.now(),
            source_timestamp=None,
            payload=None)
        for i, event_type in enumerate(event_types)]

    engine = ModuleEngine()
    comm = await hat.event.server.communication.create(comm_conf, engine)
    client = await hat.event.client.connect(comm_address, subscriptions)
    await client.query(common.QueryData())  # process `Subscribe` message

    engine.notify(events)
    if filtered_event_types:
        events = await client.receive()
        assert ({tuple(i.event_type) for i in events} ==
                {tuple(i) for i in filtered_event_types})

    await client.async_close()
    await comm.async_close()
    await engine.async_close()


async def test_without_subscribe(comm_address, comm_conf):
    event_types = [(),
                   ('a',),
                   ('b',),
                   ('a', 'a'),
                   ('a', 'b'),
                   ('a', 'b', 'c'),
                   ('', '', '')]
    events = [
        hat.event.common.Event(
            event_id=hat.event.common.EventId(server=0, instance=i),
            event_type=event_type,
            timestamp=common.now(),
            source_timestamp=None,
            payload=None)
        for i, event_type in enumerate(event_types)]

    engine = ModuleEngine()
    comm = await hat.event.server.communication.create(comm_conf, engine)
    client = await hat.event.client.connect(comm_address)
    await client.query(common.QueryData())

    engine.notify(events)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client.receive(), 0.01)

    await client.async_close()
    await comm.async_close()
    await engine.async_close()


@pytest.mark.parametrize("client_count", [1, 2, 5])
async def test_communication_events(comm_address, comm_conf, client_count):

    register_queue = aio.Queue()

    def register_cb(source, events):
        register_queue.put_nowait((source, events))
        return [None for event in events]

    engine = ModuleEngine(register_cb=register_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(register_queue.get(), 0.01)

    source_clients = []
    for _ in range(client_count):
        client = await hat.event.client.connect(comm_address)
        source, events = await register_queue.get()

        assert len(events) == 1
        assert events[0].event_type == ('event', 'communication', 'connected')
        assert source not in [i for i, _ in source_clients]

        source_clients.append((source, client))

    while source_clients:
        source_client, source_clients = source_clients[0], source_clients[1:]
        source, client = source_client

        await client.async_close()

        register_source, events = await register_queue.get()
        assert len(events) == 1
        assert events[0].event_type == ('event', 'communication',
                                        'disconnected')
        assert register_source == source

    await comm.async_close()
    await engine.async_close()


async def test_register(comm_address, comm_conf):
    register_events = [
        hat.event.common.RegisterEvent(
            event_type=('test', 'a'),
            source_timestamp=None,
            payload=None),
        hat.event.common.RegisterEvent(
            event_type=('test', 'a'),
            source_timestamp=hat.event.common.Timestamp(s=0, us=0),
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.JSON,
                data={'a': True, 'b': [0, 1, None, 'c']})),
        hat.event.common.RegisterEvent(
            event_type=('test', 'b'),
            source_timestamp=None,
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.BINARY,
                data=b'Test')),
        hat.event.common.RegisterEvent(
            event_type=('test',),
            source_timestamp=None,
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.SBS,
                data=hat.event.common.SbsData(module=None, type='Bytes',
                                              data=b'Test')))]

    register_queue = aio.Queue()

    def register_cb(source, events):
        register_queue.put_nowait(events)
        return [None for event in events]

    engine = ModuleEngine(register_cb=register_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)
    client = await hat.event.client.connect(comm_address)

    events = await register_queue.get()
    assert len(events) == 1
    assert events[0].event_type == ('event', 'communication', 'connected')

    client.register(register_events)

    events = await register_queue.get()
    assert events == register_events

    await client.async_close()

    events = await register_queue.get()
    assert len(events) == 1
    assert events[0].event_type == ('event', 'communication', 'disconnected')

    await comm.async_close()
    await engine.async_close()


async def test_register_with_response(comm_address, comm_conf):
    event_types = [(),
                   ('a',),
                   ('b',),
                   ('a', 'a'),
                   ('a', 'b'),
                   ('a', 'b', 'c'),
                   ('', '', '')]
    register_events = [
        hat.event.common.RegisterEvent(
            event_type=event_type,
            source_timestamp=None,
            payload=None)
        for event_type in event_types]

    register_queue = aio.Queue()

    def register_cb(source, events):
        register_queue.put_nowait(events)
        process_events = [engine.create_process_event(source, event)
                          for event in events]
        return [common.Event(event_id=i.event_id,
                             event_type=i.event_type,
                             timestamp=common.now(),
                             source_timestamp=i.source_timestamp,
                             payload=i.payload)
                for i in process_events]

    engine = ModuleEngine(register_cb=register_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)
    client = await hat.event.client.connect(comm_address)

    events = await register_queue.get()
    assert len(events) == 1
    assert events[0].event_type == ('event', 'communication', 'connected')

    events = await client.register_with_response(register_events)

    temp_register_events = await register_queue.get()
    assert temp_register_events == register_events

    assert [i.event_type for i in events] == event_types

    await client.async_close()

    events = await register_queue.get()
    assert len(events) == 1
    assert events[0].event_type == ('event', 'communication', 'disconnected')

    await comm.async_close()
    await engine.async_close()


async def test_register_with_response_failure(comm_address, comm_conf):
    event_types = [(),
                   ('a',),
                   ('b',),
                   ('a', 'a'),
                   ('a', 'b'),
                   ('a', 'b', 'c'),
                   ('', '', '')]
    register_events = [
        hat.event.common.RegisterEvent(
            event_type=event_type,
            source_timestamp=None,
            payload=None)
        for event_type in event_types]

    register_queue = aio.Queue()

    def register_cb(source, events):
        register_queue.put_nowait(events)
        return [None for _ in events]

    engine = ModuleEngine(register_cb=register_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)
    client = await hat.event.client.connect(comm_address)

    events = await register_queue.get()
    assert len(events) == 1
    assert events[0].event_type == ('event', 'communication', 'connected')

    events = await client.register_with_response(register_events)

    temp_register_events = await register_queue.get()
    assert temp_register_events == register_events

    assert events == [None] * len(register_events)

    await client.async_close()

    events = await register_queue.get()
    assert len(events) == 1
    assert events[0].event_type == ('event', 'communication', 'disconnected')

    await comm.async_close()
    await engine.async_close()


async def test_query(comm_address, comm_conf):
    event_types = [(),
                   ('a',),
                   ('b',),
                   ('a', 'a'),
                   ('a', 'b'),
                   ('a', 'b', 'c'),
                   ('', '', '')]
    events = [
        hat.event.common.Event(
            event_id=hat.event.common.EventId(server=0, instance=i),
            event_type=event_type,
            timestamp=common.now(),
            source_timestamp=None,
            payload=None)
        for i, event_type in enumerate(event_types)]
    query_data = common.QueryData()

    query_queue = aio.Queue()

    def query_cb(data):
        query_queue.put_nowait(data)
        return events

    engine = ModuleEngine(query_cb=query_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)
    client = await hat.event.client.connect(comm_address)

    result = await client.query(query_data)
    assert result == events

    temp_query_data = await query_queue.get()
    assert temp_query_data == query_data

    await client.async_close()
    await comm.async_close()
    await engine.async_close()
