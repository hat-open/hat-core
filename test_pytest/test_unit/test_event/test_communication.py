import pytest
import asyncio
import functools

import hat.chatter
import hat.event.client
import hat.event.common
import hat.event.server.common
import hat.event.server.communication

from hat import aio
from test_unit.test_event import common


@pytest.fixture
def comm_conf(unused_tcp_port_factory):
    return {
        'address': f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}'}


@pytest.fixture
def register_events():
    return [
        hat.event.common.RegisterEvent(
            event_type=['test', 'a'],
            source_timestamp=None,
            payload=None),
        hat.event.common.RegisterEvent(
            event_type=['test', 'a'],
            source_timestamp=hat.event.common.Timestamp(s=0, us=0),
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.JSON,
                data={'a': True, 'b': [0, 1, None, 'c']})),
        hat.event.common.RegisterEvent(
            event_type=['test', 'b'],
            source_timestamp=None,
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.BINARY,
                data=b'Test')),
        hat.event.common.RegisterEvent(
            event_type=['test'],
            source_timestamp=None,
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.SBS,
                data=hat.event.common.SbsData(module=None, type='Bytes',
                                              data=b'Test')))]


@pytest.mark.asyncio
async def test_client_connect_disconnect(comm_conf):

    with pytest.raises(Exception):
        await hat.event.client.connect(comm_conf['address'])

    engine = common.create_module_engine()
    comm = await hat.event.server.communication.create(comm_conf, engine)
    assert not comm.is_closed

    client = await hat.event.client.connect(comm_conf['address'])
    assert not client.is_closed

    await client.async_close()
    await comm.async_close()
    await engine.async_close()

    assert client.is_closed
    assert comm.is_closed

    with pytest.raises(Exception):
        await hat.event.client.connect(comm_conf['address'])


@pytest.mark.skip(reason='communication events - regresion failure')
@pytest.mark.asyncio
async def test_srv_comm_close(comm_conf, register_events):
    comm_register = asyncio.Event()
    comm_query = asyncio.Event()

    async def unresponsive_cb(async_event, _):
        async_event.set()
        while True:
            await asyncio.sleep(1)

    engine = common.create_module_engine(
        register_cb=functools.partial(unresponsive_cb, comm_register),
        query_cb=functools.partial(unresponsive_cb, comm_query))
    comm = await hat.event.server.communication.create(comm_conf, engine)
    assert not comm.is_closed

    client = await hat.event.client.connect(comm_conf['address'])
    assert not client.is_closed

    async with aio.Group() as group:
        futures = [
            group.spawn(client.receive),
            group.spawn(client.register_with_response, register_events),
            group.spawn(client.query, hat.event.common.QueryData())]

        await asyncio.gather(comm_register.wait(), comm_query.wait())

        await comm.async_close()
        await engine.async_close()
        assert comm.is_closed

        for f in futures:
            with pytest.raises(ConnectionError):
                await f

    await client.wait_closed()


@pytest.mark.parametrize("subscriptions", [
    [[]],
    [['*']],
    [['?']],
    [['?', '*']],
    [['?', '?']],
    [['?', '?', '*']],
    [['?', '?', '?']],
    [['?', '?', '?', '*']],
    [['a']],
    [['a', '*']],
    [['a', '?']],
    [['a', '?', '*']],
    [['a', '?', '?']],
    [['a', 'b']],
    [['a', 'b', '*']],
    [['a', 'b', '?']],
    [['?', 'b']],
    [['?', 'b', '?']],
    [['?', 'b', '*']],
    [['a', 'b', 'c']],
    [['a'], []],
    [['a'], ['*']],
    [['a'], ['?']],
    [['a'], ['b']],
    [['a'], ['a', 'a']],
    [['a'], ['a', 'b']],
    [['b'], ['a', 'b']],
    [['a'], ['a', 'b'], ['a', 'b', 'c']],
    [['', '', '']]])
@pytest.mark.asyncio
async def test_subscribe(comm_conf, subscriptions):
    event_types = [
        [],
        ['a'],
        ['b'],
        ['a', 'a'],
        ['a', 'b'],
        ['a', 'b', 'c'],
        ['', '', '']]

    engine = common.create_module_engine()
    comm = await hat.event.server.communication.create(comm_conf, engine)

    client = await hat.event.client.connect(comm_conf['address'],
                                            subscriptions=subscriptions)

    await asyncio.sleep(0.01)  # allow server to receive `Subscribe` message

    engine._register_event_cbs.notify([
        hat.event.common.Event(
            event_id=hat.event.common.EventId(server=0, instance=i),
            event_type=event_type,
            timestamp=hat.event.common.Timestamp(s=0, us=0),
            source_timestamp=None,
            payload=None
        ) for i, event_type in enumerate(event_types)])

    filtered_event_types = [
        event_type for event_type in event_types
        if any(hat.event.common.matches_query_type(event_type, query_type)
               for query_type in subscriptions)]

    if filtered_event_types:
        events = await client.receive()
        assert (set((tuple(i.event_type) for i in events)) ==
                set(tuple(i) for i in filtered_event_types))

    await client.async_close()
    await comm.async_close()
    await engine.async_close()


@pytest.mark.asyncio
async def test_register(comm_conf, register_events):

    def register_cb(events):
        events = [i for i in events
                  if i.event_type[:2] != ['event', 'communication']]
        if not events:
            return []
        register_queue.put_nowait(events)
        return [common.process_event_to_event(i) for i in events]

    register_queue = aio.Queue()
    engine = common.create_module_engine(register_cb=register_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)

    client = await hat.event.client.connect(comm_conf['address'],
                                            subscriptions=[['test', '*']])

    client.register(register_events)
    process_events = await register_queue.get()

    assert all(type(event) == hat.event.server.common.ProcessEvent
               for event in process_events)
    assert all(common.compare_register_event_vs_event(r, p)
               for r, p in zip(register_events, process_events))

    events = [common.process_event_to_event(i) for i in process_events]
    subscription_events = await client.receive()
    assert events == subscription_events

    await client.async_close()
    await comm.async_close()
    await engine.async_close()


@pytest.mark.asyncio
async def test_register_with_response(comm_conf, register_events):

    def register_cb(events):
        events = [i for i in events
                  if i.event_type[:2] != ['event', 'communication']]
        if not events:
            return []
        register_queue.put_nowait(events)
        return [common.process_event_to_event(i) for i in events]

    register_queue = aio.Queue()
    engine = common.create_module_engine(register_cb=register_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)

    client = await hat.event.client.connect(comm_conf['address'],
                                            subscriptions=[['test', '*']])

    client_events = await client.register_with_response(register_events)
    process_events = await register_queue.get()

    assert all(type(event) == hat.event.server.common.ProcessEvent
               for event in process_events)
    assert all(common.compare_register_event_vs_event(r, p)
               for r, p in zip(register_events, process_events))

    events = [common.process_event_to_event(i) for i in process_events]
    assert events == client_events

    subscription_events = await client.receive()
    assert events == subscription_events

    await client.async_close()
    await comm.async_close()
    await engine.async_close()


@pytest.mark.asyncio
async def test_query(comm_conf):

    def query_cb(data):
        query_queue.put_nowait(data)
        return mock_result

    mock_query = hat.event.common.QueryData()
    mock_result = [hat.event.common.Event(
        event_id=hat.event.common.EventId(server=0, instance=0),
        event_type=['mock'],
        timestamp=hat.event.common.Timestamp(s=0, us=0),
        source_timestamp=None,
        payload=None)]
    query_queue = aio.Queue()

    engine = common.create_module_engine(query_cb=query_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)
    client = await hat.event.client.connect(comm_conf['address'])

    events = await client.query(mock_query)
    query_data = await query_queue.get()

    assert events == mock_result
    assert query_data == mock_query

    await client.async_close()
    await comm.async_close()
    await engine.async_close()


@pytest.mark.asyncio
async def test_communication_event(comm_conf):

    def register_cb(events):
        register_queue.put_nowait(events)
        return [common.process_event_to_event(i) for i in events]

    register_queue = aio.Queue()
    engine = common.create_module_engine(register_cb=register_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)
    clients_count = 10

    clients = []
    for i in range(clients_count):
        client = await hat.event.client.connect(comm_conf['address'])
        clients.append(client)
        events = await register_queue.get()
        event = events[0]

        assert event.event_type == ['event', 'communication', 'connected']
        assert event.payload is None
        assert event.source.id == i + 1

    for i in reversed(range(clients_count)):
        client = clients.pop()
        await client.async_close()

        events = await register_queue.get()
        event = events[0]

        assert event.event_type == ['event', 'communication', 'disconnected']
        assert event.payload is None
        assert event.source.id == i + 1

    await comm.async_close()
    await engine.async_close()
