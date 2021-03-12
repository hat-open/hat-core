import asyncio

import pytest

from hat.event.server.backends.lmdb import common
import hat.event.server.backends.lmdb.backend


pytestmark = pytest.mark.asyncio


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / 'db'


@pytest.fixture
def create_event():
    counter = 0

    def create_event(event_type):
        nonlocal counter
        counter += 1
        event_id = common.EventId(1, counter)
        t = common.now()
        event = common.Event(event_id=event_id,
                             event_type=event_type,
                             timestamp=t,
                             source_timestamp=t,
                             payload=None)
        return event

    return create_event


async def test_create_empty(db_path):
    conf = {'db_path': str(db_path),
            'max_db_size': 1024 * 1024 * 1024,
            'sync_period': 30,
            'server_id': 1,
            'conditions': [],
            'latest': {'subscriptions': [['*']]},
            'ordered': [{'order_by': 'TIMESTAMP',
                         'subscriptions': [['*']]}]}

    backend = await hat.event.server.backends.lmdb.backend.create(conf)

    assert backend.is_open

    await backend.async_close()


async def test_get_last_event_id(db_path, create_event):
    server_id = 1
    conf = {'db_path': str(db_path),
            'max_db_size': 1024 * 1024 * 1024,
            'sync_period': 30,
            'server_id': server_id,
            'conditions': [],
            'latest': {'subscriptions': [['*']]},
            'ordered': [{'order_by': 'TIMESTAMP',
                         'subscriptions': [['*']]}]}

    backend = await hat.event.server.backends.lmdb.backend.create(conf)

    event_id = await backend.get_last_event_id(server_id)
    assert event_id == common.EventId(server_id, 0)

    event_id = await backend.get_last_event_id(server_id + 1)
    assert event_id == common.EventId(server_id + 1, 0)

    event = create_event(('a',))
    await backend.register([event])

    event_id = await backend.get_last_event_id(server_id)
    assert event_id == event.event_id

    event_id = await backend.get_last_event_id(server_id + 1)
    assert event_id == common.EventId(server_id + 1, 0)

    await backend.async_close()

    backend = await hat.event.server.backends.lmdb.backend.create(conf)

    event_id = await backend.get_last_event_id(server_id)
    assert event_id == event.event_id

    await backend.async_close()


async def test_register(db_path, create_event):
    conf = {'db_path': str(db_path),
            'max_db_size': 1024 * 1024 * 1024,
            'sync_period': 30,
            'server_id': 1,
            'conditions': [{'subscriptions': [('f',)],
                            'condition': {'type': 'json'}}],
            'latest': {'subscriptions': [['*']]},
            'ordered': [{'order_by': 'TIMESTAMP',
                         'subscriptions': [['*']]}]}

    backend = await hat.event.server.backends.lmdb.backend.create(conf)

    result = await backend.query(common.QueryData())
    assert result == []

    event1 = create_event(('a',))
    await asyncio.sleep(0.001)
    event2 = create_event(('b',))._replace(event_id=common.EventId(2, 1))
    await asyncio.sleep(0.001)
    event3 = create_event(('c',))._replace(event_id=event1.event_id)
    await asyncio.sleep(0.001)
    event4 = create_event(('d',))
    await asyncio.sleep(0.001)
    event5 = create_event(('e',))._replace(timestamp=event1.timestamp)
    await asyncio.sleep(0.001)
    event6 = create_event(('f',))
    await asyncio.sleep(0.001)
    event7 = create_event(('g',))
    await asyncio.sleep(0.001)

    events = [event1, event2, event3, event4, event5, event6, event7]
    result = await backend.register(events)
    assert result == events

    result = await backend.query(common.QueryData())
    assert result == [event7, event4, event1]

    await backend.async_close()

    backend = await hat.event.server.backends.lmdb.backend.create(conf)

    result = await backend.query(common.QueryData())
    assert result == [event7, event4, event1]

    await backend.async_close()


async def test_query(db_path, create_event):
    conf = {'db_path': str(db_path),
            'max_db_size': 1024 * 1024 * 1024,
            'sync_period': 30,
            'server_id': 1,
            'conditions': [],
            'latest': {'subscriptions': [['*']]},
            'ordered': [{'order_by': 'TIMESTAMP',
                         'subscriptions': [['*']]},
                        {'order_by': 'SOURCE_TIMESTAMP',
                         'subscriptions': [['*']]}]}

    backend = await hat.event.server.backends.lmdb.backend.create(conf)

    event1 = create_event(('a',))
    event2 = create_event(('a',))
    event3 = create_event(('a',))

    events = [event1, event2, event3]
    result = await backend.register(events)
    assert result == events

    result = await backend.query(common.QueryData())
    assert result == [event3, event2, event1]

    result = await backend.query(common.QueryData(
        order_by=common.OrderBy.SOURCE_TIMESTAMP))
    assert result == [event3, event2, event1]

    result = await backend.query(common.QueryData(unique_type=True))
    assert result == [event3]

    result = await backend.query(common.QueryData(t_from=event1.timestamp,
                                                  unique_type=True,
                                                  max_results=1))
    assert result == [event3]

    await backend.async_close()


async def test_query_partitioning(db_path, create_event):
    conf = {'db_path': str(db_path),
            'max_db_size': 1024 * 1024 * 1024,
            'sync_period': 30,
            'server_id': 1,
            'conditions': [],
            'latest': {'subscriptions': [['*']]},
            'ordered': [{'order_by': 'TIMESTAMP',
                         'subscriptions': [['a']]},
                        {'order_by': 'TIMESTAMP',
                         'subscriptions': [['b']]}]}

    backend = await hat.event.server.backends.lmdb.backend.create(conf)

    event1 = create_event(('a',))
    event2 = create_event(('b',))

    events = [event1, event2]
    result = await backend.register(events)
    assert result == events

    result = await backend.query(common.QueryData(event_types=[('a',)]))
    assert result == [event1]

    result = await backend.query(common.QueryData(event_types=[('b',)]))
    assert result == [event2]

    result = await backend.query(common.QueryData(event_types=[('*',)]))
    assert result == [event1]

    await backend.async_close()
