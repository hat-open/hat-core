import datetime

import lmdb
import pytest

from hat import aio
from hat.event.server.backends.lmdb import common
import hat.event.server.backends.lmdb.conditions
import hat.event.server.backends.lmdb.latestdb


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

    async def flush(db):
        txn = await executor(env.begin, write=True)
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            await executor(db.create_ext_flush(), txn, now)
        finally:
            await executor(txn.commit)

    return flush


@pytest.fixture
def create_event():
    counter = 0

    def create_event(event_type, payload):
        nonlocal counter
        counter += 1
        event_id = common.EventId(1, counter)
        event = common.Event(event_id=event_id,
                             event_type=event_type,
                             timestamp=common.now(),
                             source_timestamp=None,
                             payload=payload)
        return event

    return create_event


async def test_create_empty(executor, env):
    name = 'name'
    subscription = common.Subscription([])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.latestdb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions)

    assert db.subscription == subscription
    result = list(db.query(None))
    assert result == []


async def test_add(executor, env, flush, create_event):
    name = 'name'
    subscription = common.Subscription([('*',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.latestdb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions)

    result = list(db.query(None))
    assert result == []

    event1 = create_event(('a',), None)
    db.add(event1)

    result = set(db.query(None))
    assert result == {event1}

    event2 = create_event(('b',), None)
    db.add(event2)

    result = set(db.query(None))
    assert result == {event1, event2}

    event3 = create_event(('a',), None)
    db.add(event3)

    result = set(db.query(None))
    assert result == {event2, event3}

    await flush(db)

    db = await hat.event.server.backends.lmdb.latestdb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions)

    result = set(db.query(None))
    assert result == {event2, event3}


async def test_query(executor, env, flush, create_event):
    name = 'name'
    subscription = common.Subscription([('a',), ('b',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.latestdb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions)

    event1 = create_event(('a',), None)
    event2 = create_event(('b',), None)
    event3 = create_event(('c',), None)

    db.add(event1)
    db.add(event2)
    db.add(event3)

    result = set(db.query(None))
    assert result == {event1, event2}

    result = set(db.query([('a',), ('b',), ('c',)]))
    assert result == {event1, event2}

    result = set(db.query([('*',)]))
    assert result == {event1, event2}

    result = set(db.query([('a',)]))
    assert result == {event1}

    result = set(db.query([('b',)]))
    assert result == {event2}

    result = set(db.query([('c',)]))
    assert result == set()


async def test_subscription_change(executor, env, flush, create_event):
    name = 'name'
    subscription1 = common.Subscription([('a',)])
    subscription2 = common.Subscription([('b',)])
    conditions = hat.event.server.backends.lmdb.conditions.Conditions([])
    db = await hat.event.server.backends.lmdb.latestdb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription1,
        conditions=conditions)

    event = create_event(('a',), None)
    db.add(event)

    await flush(db)

    db = await hat.event.server.backends.lmdb.latestdb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription1,
        conditions=conditions)

    result = set(db.query(None))
    assert result == {event}

    db = await hat.event.server.backends.lmdb.latestdb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription2,
        conditions=conditions)

    result = set(db.query(None))
    assert result == set()


async def test_conditions_change(executor, env, flush, create_event):
    name = 'name'
    subscription = common.Subscription([('*',)])
    conditions1 = hat.event.server.backends.lmdb.conditions.Conditions([])
    conditions2 = hat.event.server.backends.lmdb.conditions.Conditions([{
        'subscriptions': [['*']],
        'condition': {'type': 'json'}}])
    db = await hat.event.server.backends.lmdb.latestdb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions1)

    event = create_event(('a',), None)
    db.add(event)

    await flush(db)

    db = await hat.event.server.backends.lmdb.latestdb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions1)

    result = set(db.query(None))
    assert result == {event}

    db = await hat.event.server.backends.lmdb.latestdb.create(
        executor=executor,
        env=env,
        name=name,
        subscription=subscription,
        conditions=conditions2)

    result = set(db.query(None))
    assert result == set()
