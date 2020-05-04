import pytest
import asyncio
import functools

import hat.chatter
import hat.event.client
import hat.event.common
import hat.event.server.common
import hat.event.server.communication

from hat.util import aio
from test_unit.test_event import common


@pytest.fixture
def comm_conf(unused_tcp_port_factory):
    return {
        'address': f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}'}


@pytest.fixture
def register_events():
    return [
        hat.event.common.RegisterEvent(
            event_type=['a'],
            source_timestamp=None,
            payload=None),
        hat.event.common.RegisterEvent(
            event_type=['a'],
            source_timestamp=hat.event.common.Timestamp(s=0, us=0),
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.JSON,
                data={'a': True, 'b': [0, 1, None, 'c']})),
        hat.event.common.RegisterEvent(
            event_type=['b'],
            source_timestamp=None,
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.BINARY,
                data=b'Test')),
        hat.event.common.RegisterEvent(
            event_type=[],
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
    assert not comm.closed.done()

    client = await hat.event.client.connect(comm_conf['address'])
    assert not client.closed.done()

    await client.async_close()
    await comm.async_close()
    await engine.async_close()

    assert client.closed.done()
    assert comm.closed.done()

    with pytest.raises(Exception):
        await hat.event.client.connect(comm_conf['address'])


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
    assert not comm.closed.done()

    client = await hat.event.client.connect(comm_conf['address'])
    assert not client.closed.done()

    async with aio.Group() as group:
        futures = [
            group.spawn(client.receive),
            group.spawn(client.register_with_response, register_events),
            group.spawn(client.query, hat.event.common.QueryData())]

        await asyncio.gather(comm_register.wait(), comm_query.wait())

        await comm.async_close()
        await engine.async_close()
        assert comm.closed.done()

        for f in futures:
            with pytest.raises(hat.chatter.ConnectionClosedError):
                await f

    await client.closed


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
    ['', '', '']])
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
        register_queue.put_nowait(events)
        return [common.process_event_to_event(i) for i in events]

    register_queue = aio.Queue()
    engine = common.create_module_engine(register_cb=register_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)

    client = await hat.event.client.connect(comm_conf['address'],
                                            subscriptions=['*'])

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
        register_queue.put_nowait(events)
        return [common.process_event_to_event(i) for i in events]

    register_queue = aio.Queue()
    engine = common.create_module_engine(register_cb=register_cb)
    comm = await hat.event.server.communication.create(comm_conf, engine)

    client = await hat.event.client.connect(comm_conf['address'],
                                            subscriptions=['*'])

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
