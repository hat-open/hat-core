import asyncio

import lmdb
import pytest

from hat import aio
from hat.event.server.backends.lmdb import common
import hat.event.server.backends.lmdb.conditions
import hat.event.server.backends.lmdb.ordereddb


pytestmark = pytest.mark.asyncio


db_map_size = 1024 * 1024 * 1024
db_max_dbs = 32


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / 'db'


@pytest.fixture
async def executor():
    return aio.create_executor(1)


@pytest.fixture
async def env(executor, db_path):
    env = await executor(lmdb.Environment, str(db_path),
                         map_size=db_map_size, subdir=False,
                         max_dbs=db_max_dbs)
    try:
        yield env
    finally:
        await executor(env.close)


@pytest.fixture
def flush(executor, env):

    async def flush(db, now=None):
        txn = await executor(env.begin, write=True)
        if now is None:
            now = common.now()
        try:
            await executor(db.create_ext_flush(), txn, now)
        finally:
            await executor(txn.commit)

    return flush


@pytest.fixture
def query(executor, env):

    async def query(db, subscription=None, event_ids=None, t_from=None,
                    t_to=None, source_t_from=None, source_t_to=None,
                    payload=None, order=common.Order.DESCENDING,
                    unique_type=False, max_results=None):
        return list(await db.query(subscription=subscription,
                                   event_ids=event_ids,
                                   t_from=t_from,
                                   t_to=t_to,
                                   source_t_from=source_t_from,
                                   source_t_to=source_t_to,
                                   payload=payload,
                                   order=order,
                                   unique_type=unique_type,
                                   max_results=max_results))

    return query


@pytest.fixture
def create_event():
    counter = 0

    def create_event(event_type, with_source_timestamp):
        nonlocal counter
        counter += 1
        event_id = common.EventId(1, counter)
        t = common.now()
        event = common.Event(event_id=event_id,
                             event_type=event_type,
                             timestamp=t,
                             source_timestamp=(t if with_source_timestamp
                                               else None),
                             payload=None)
        return event

    return create_event


@pytest.mark.parametrize('order_by', common.OrderBy)
async def test_create_empty(executor, env, query, order_by):
    name = 'name'
    subscription = common.Subscription([])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=None)

    assert db.subscription == subscription
    assert db.order_by == order_by
    result = await query(db)
    assert result == []


@pytest.mark.parametrize('order_by', common.OrderBy)
async def test_add(executor, env, flush, query, create_event, order_by):
    name = 'name'
    subscription = common.Subscription([('a',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=None)

    event1 = create_event(('a',), True)
    event2 = create_event(('b',), True)
    event3 = create_event(('a',), False)
    event4 = create_event(('a',), True)

    db.add(event1)
    db.add(event2)

    result = await query(db)
    assert result == [event1]

    await flush(db)

    db.add(event3)
    db.add(event4)

    result = await query(db)
    if order_by == common.OrderBy.TIMESTAMP:
        assert result == [event4, event3, event1]
    elif order_by == common.OrderBy.SOURCE_TIMESTAMP:
        assert result == [event4, event1]


@pytest.mark.parametrize('order_by', common.OrderBy)
@pytest.mark.parametrize('order', common.Order)
async def test_query_max_results(executor, env, flush, query, create_event,
                                 order_by, order):
    name = 'name'
    subscription = common.Subscription([('a',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=None)

    event1 = create_event(('a',), True)
    event2 = create_event(('a',), True)
    event3 = create_event(('a',), True)

    result = await query(db, max_results=2, order=order)
    assert result == []

    db.add(event1)

    result = await query(db, max_results=2, order=order)
    assert result == [event1]

    await flush(db)

    result = await query(db, max_results=2, order=order)
    assert result == [event1]

    db.add(event2)

    result = await query(db, max_results=2, order=order)
    if order == common.Order.DESCENDING:
        assert result == [event2, event1]
    elif order == common.Order.ASCENDING:
        assert result == [event1, event2]

    db.add(event3)

    result = await query(db, max_results=2, order=order)
    if order == common.Order.DESCENDING:
        assert result == [event3, event2]
    elif order == common.Order.ASCENDING:
        assert result == [event1, event2]

    await flush(db)

    result = await query(db, max_results=2, order=order)
    if order == common.Order.DESCENDING:
        assert result == [event3, event2]
    elif order == common.Order.ASCENDING:
        assert result == [event1, event2]


@pytest.mark.parametrize('order_by', common.OrderBy)
@pytest.mark.parametrize('order', common.Order)
async def test_query_timestamps(executor, env, flush, query, create_event,
                                order_by, order):
    name = 'name'
    subscription = common.Subscription([('a',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=None)

    event1 = create_event(('a',), True)
    await asyncio.sleep(0.001)
    event2 = create_event(('a',), True)
    await asyncio.sleep(0.001)
    event3 = create_event(('a',), True)
    await asyncio.sleep(0.001)
    event4 = create_event(('a',), True)
    await asyncio.sleep(0.001)

    db.add(event1)
    db.add(event2)
    db.add(event3)
    db.add(event4)

    for _ in range(2):
        result = await query(db, order=order)
        if order == common.Order.DESCENDING:
            assert result == [event4, event3, event2, event1]
        elif order == common.Order.ASCENDING:
            assert result == [event1, event2, event3, event4]

        result = await query(db, order=order,
                             t_from=event2.timestamp)
        if order == common.Order.DESCENDING:
            assert result == [event4, event3, event2]
        elif order == common.Order.ASCENDING:
            assert result == [event2, event3, event4]

        result = await query(db, order=order,
                             source_t_from=event2.source_timestamp)
        if order == common.Order.DESCENDING:
            assert result == [event4, event3, event2]
        elif order == common.Order.ASCENDING:
            assert result == [event2, event3, event4]

        result = await query(db, order=order,
                             t_to=event3.timestamp)
        if order == common.Order.DESCENDING:
            assert result == [event3, event2, event1]
        elif order == common.Order.ASCENDING:
            assert result == [event1, event2, event3]

        result = await query(db, order=order,
                             source_t_to=event3.source_timestamp)
        if order == common.Order.DESCENDING:
            assert result == [event3, event2, event1]
        elif order == common.Order.ASCENDING:
            assert result == [event1, event2, event3]

        result = await query(db, order=order,
                             t_from=event1.timestamp, t_to=event4.timestamp,
                             source_t_from=event1.source_timestamp,
                             source_t_to=event4.source_timestamp)
        if order == common.Order.DESCENDING:
            assert result == [event4, event3, event2, event1]
        elif order == common.Order.ASCENDING:
            assert result == [event1, event2, event3, event4]

        t = common.now()
        result = await query(db, order=order,
                             t_from=t, t_to=t,
                             source_t_from=t,
                             source_t_to=t)
        assert result == []

        await flush(db)


@pytest.mark.parametrize('order_by', common.OrderBy)
async def test_query_subscription(executor, env, flush, query, create_event,
                                  order_by):
    name = 'name'
    subscription = common.Subscription([('*',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=None)

    event1 = create_event(('a',), True)
    event2 = create_event(('b',), True)

    db.add(event1)
    db.add(event2)

    result = await query(db)
    assert result == [event2, event1]

    subscription = common.Subscription([('a',)])
    result = await query(db, subscription=subscription)
    assert result == [event1]

    subscription = common.Subscription([('b',)])
    result = await query(db, subscription=subscription)
    assert result == [event2]


@pytest.mark.parametrize('order_by', common.OrderBy)
async def test_query_event_ids(executor, env, flush, query, create_event,
                               order_by):
    name = 'name'
    subscription = common.Subscription([('*',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=None)

    event1 = create_event(('a',), True)
    event2 = create_event(('b',), True)

    db.add(event1)
    db.add(event2)

    result = await query(db)
    assert result == [event2, event1]

    result = await query(db, event_ids=[])
    assert result == []

    result = await query(db, event_ids=[event1.event_id])
    assert result == [event1]

    result = await query(db, event_ids=[event2.event_id])
    assert result == [event2]

    result = await query(db, event_ids=[event1.event_id, event2.event_id])
    assert result == [event2, event1]


@pytest.mark.parametrize('order_by', common.OrderBy)
async def test_query_payload(executor, env, flush, query, create_event,
                             order_by):
    name = 'name'
    subscription = common.Subscription([('*',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=None)

    event1 = create_event(('a',), True)
    event2 = create_event(('b',), True)._replace(payload=common.EventPayload(
        common.EventPayloadType.JSON,
        data=123))

    db.add(event1)
    db.add(event2)

    result = await query(db)
    assert result == [event2, event1]

    result = await query(db, payload=common.EventPayload(
        common.EventPayloadType.JSON,
        data=123))
    assert result == [event2]

    result = await query(db, payload=common.EventPayload(
        common.EventPayloadType.JSON,
        data=321))
    assert result == []


@pytest.mark.parametrize('order_by', common.OrderBy)
async def test_query_unique_type(executor, env, flush, query, create_event,
                                 order_by):
    name = 'name'
    subscription = common.Subscription([('*',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=None)

    event1 = create_event(('a',), True)
    event2 = create_event(('b',), True)
    event3 = create_event(('a',), True)
    event4 = create_event(('b',), True)

    db.add(event1)
    db.add(event2)
    db.add(event3)
    db.add(event4)

    result = await query(db)
    assert result == [event4, event3, event2, event1]

    result = await query(db, unique_type=True)
    assert result == [event4, event3]


@pytest.mark.parametrize('order_by', common.OrderBy)
async def test_limit_max_entries(executor, env, flush, query, create_event,
                                 order_by):
    name = 'name'
    subscription = common.Subscription([('*',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    limit = {'max_entries': 3}
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=limit)

    for i in range(limit['max_entries'] * 2):
        db.add(create_event(('a',), True))
        await flush(db)

        expected_len = (i + 1 if i < limit['max_entries']
                        else limit['max_entries'])
        result = await query(db)
        assert expected_len == len(result)


@pytest.mark.parametrize('order_by', common.OrderBy)
async def test_limit_min_entries(executor, env, flush, query, create_event,
                                 order_by):
    name = 'name'
    subscription = common.Subscription([('*',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    limit = {'min_entries': 5,
             'max_entries': 3}
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=limit)

    for i in range(limit['min_entries'] * 2):
        db.add(create_event(('a',), True))
        await flush(db)

        expected_len = (i + 1 if i < limit['min_entries']
                        else limit['min_entries'])
        result = await query(db)
        assert expected_len == len(result)


@pytest.mark.parametrize('order_by', common.OrderBy)
async def test_limit_duration(executor, env, flush, query, create_event,
                              order_by):
    name = 'name'
    subscription = common.Subscription([('*',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    limit = {'duration': 1}
    db = await hat.event.server.backends.lmdb.ordereddb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions,
        order_by=order_by,
        limit=limit)

    t1 = common.now()
    t2 = t1._replace(s=t1.s + 2 * limit['duration'])
    t3 = t2._replace(s=t2.s + 2 * limit['duration'])

    event1 = create_event(('a',), True)._replace(timestamp=t1,
                                                 source_timestamp=t1)
    event2 = create_event(('a',), True)._replace(timestamp=t2,
                                                 source_timestamp=t2)

    db.add(event1)
    db.add(event2)

    result = await query(db)
    assert result == [event2, event1]

    await flush(db, t2)

    result = await query(db)
    assert result == [event2]

    await flush(db, t3)

    result = await query(db)
    assert result == []


@pytest.mark.parametrize('order_by', common.OrderBy)
async def test_limit_size(executor, env, flush, query, create_event, order_by):
    # TODO
    pass
