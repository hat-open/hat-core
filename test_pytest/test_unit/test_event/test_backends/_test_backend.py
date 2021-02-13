import pytest
import importlib
import itertools

import hat.event.common
import hat.event.server.common


ts0 = hat.event.common.now()
ts1 = ts0._replace(s=ts0.s + 10)
ts2 = ts1._replace(s=ts1.s + 10)


def before(ts):
    return ts._replace(s=ts.s - 1)


def after(ts):
    return ts._replace(s=ts.s + 1)


def ts_gen(start):
    n = itertools.count()
    while True:
        yield start._replace(us=start.us + next(n))


@pytest.fixture(params=['sqlite'], scope="module")
def conf_factory(tmpdir_factory, request):

    def f():
        return {
            'sqlite':
                {'module': 'hat.event.server.backends.sqlite',
                 'db_path': tmpdir_factory.mktemp('event').join('event.db'),
                 'query_pool_size': 10}}[request.param]

    return f


@pytest.mark.asyncio
@pytest.fixture(scope="module")
async def backend_with_events(conf_factory, event_loop,
                              backend_events_factory):
    conf = conf_factory()
    backend = await importlib.import_module(conf['module']).create(conf)

    reg_events = []
    for ts in [ts0, ts1, ts2]:
        backend_events = backend_events_factory(timestamp=ts)
        await backend.register(backend_events)
        reg_events += backend_events

    yield backend, reg_events
    await backend.async_close()


@pytest.mark.asyncio
@pytest.fixture(scope="function")
async def backend(conf_factory, event_loop):
    conf = conf_factory()
    backend = await importlib.import_module(conf['module']).create(conf)
    yield backend
    await backend.async_close()


@pytest.mark.asyncio
@pytest.fixture(scope="module")
async def backend_memory_backend(conf_factory, event_loop,
                                 backend_events_factory):
    conf = conf_factory()
    backend = await importlib.import_module(conf['module']).create(conf)
    memory_backend = await importlib.import_module(
        'hat.event.server.backends.memory').create(
        {'module': 'hat.event.server.backends.memory'})

    backend_events = []
    ts = ts_gen(hat.event.common.now())
    for i in range(3):
        backend_events += backend_events_factory(timestamp=next(ts))
    await backend.register(backend_events)
    await memory_backend.register(backend_events)

    yield backend, memory_backend
    await backend.async_close()
    await memory_backend.async_close()


@pytest.fixture(scope="module")
def backend_events_factory():
    types_payloads = [
        (('1',), {'value': 1.2, 'quality': "GOOD"},
         hat.event.common.EventPayloadType.JSON),
        (('1',), {'value': 1.3, 'quality': "GOOD"},
         hat.event.common.EventPayloadType.JSON),
        (('1',), {'value': 2.8, 'quality': "GOOD"},
         hat.event.common.EventPayloadType.JSON),
        (('2',), {'value': 205, 'quality': "GOOD"},
         hat.event.common.EventPayloadType.JSON),
        (('2',), b'308', hat.event.common.EventPayloadType.BINARY),
        (('2',), hat.event.common.SbsData(module=None, type='String',
                                          data=b'ab '),
         hat.event.common.EventPayloadType.SBS),
        (('3',), [1, 2, 3], hat.event.common.EventPayloadType.JSON),
        (('4',), 'payload', hat.event.common.EventPayloadType.JSON),
        (('4',), None, hat.event.common.EventPayloadType.JSON),
        (('5',), None, hat.event.common.EventPayloadType.JSON)]
    event_id_state = {1: 0,
                      2: 0}

    def backend_events(server_id=1, timestamp=None, source_timestamp=None):
        ret = []
        ts = timestamp if timestamp else hat.event.common.now()
        source_ts = ts_gen(source_timestamp if source_timestamp else ts)
        for event_type, payload, payload_type in types_payloads:
            event_id_state[server_id] += 1
            ret.append(hat.event.server.common.Event(
                event_id=hat.event.common.EventId(
                    server=server_id,
                    instance=event_id_state[server_id]),
                event_type=event_type,
                timestamp=ts,
                source_timestamp=next(source_ts),
                payload=hat.event.common.EventPayload(type=payload_type,
                                                      data=payload)))
        return ret

    return backend_events


@pytest.mark.asyncio
async def test_register(backend, backend_events_factory):
    backend_events = backend_events_factory(server_id=1)
    register_res = await backend.register(backend_events)
    assert register_res == backend_events


@pytest.mark.asyncio
async def test_event_type_mappings(backend):
    mappings_stored = await backend.get_event_type_mappings()
    assert not mappings_stored

    mappings = {1: ('a',),
                2: ('b',),
                3: ('a', 'b'),
                4: ('a', 'c'),
                5: ('a', 'b', 'c'),
                6: ('a', 'b', 'd'),
                7: ()}
    await backend.add_event_type_mappings(mappings)
    mappings_stored = await backend.get_event_type_mappings()
    assert mappings == mappings_stored

    mappings_ = {8: ('d', 'e', 'f'),
                 9: ('g', 'h', 'i')}
    await backend.add_event_type_mappings(mappings_)
    mappings_stored = await backend.get_event_type_mappings()
    mappings.update(mappings_)
    assert mappings_stored == mappings

    # event_type_id_mappings are immutable
    mappings_ = {6: ('a', 'b', 'c', 'd'),
                 7: ('k', 'l')}
    await backend.add_event_type_mappings(mappings_)
    mappings_stored = await backend.get_event_type_mappings()
    assert mappings_stored == mappings


@pytest.mark.asyncio
async def test_get_last_event_id(backend, backend_events_factory):
    last_event_id = await backend.get_last_event_id(server_id=1)
    assert last_event_id.server == 1
    assert last_event_id.instance == 0

    registered_events1 = backend_events_factory(server_id=1)
    await backend.register(registered_events1)
    registered_events2 = backend_events_factory(server_id=2)
    await backend.register(registered_events2)

    last_event_id = await backend.get_last_event_id(server_id=1)
    assert last_event_id.server == 1
    assert last_event_id.instance == max(
        e.event_id.instance for e in registered_events1)

    last_event_id = await backend.get_last_event_id(server_id=2)
    assert last_event_id.server == 2
    assert last_event_id.instance == max(
        e.event_id.instance for e in registered_events2)


@pytest.mark.skip('WIP')
@pytest.mark.parametrize("event_ids, event_types, payload", [
    (None, None, None),
    ([hat.event.common.EventId(server=1, instance=0)], None, None),
    (None, [('1',), ('4',), ('5',)], None),
    (None, [], None),
    (None, None, hat.event.common.EventPayload(
        type=hat.event.common.EventPayloadType.JSON,
        data=None)),
    (None, None, hat.event.common.EventPayload(
        type=hat.event.common.EventPayloadType.JSON,
        data='payload')),
    (None, None, hat.event.common.EventPayload(
        type=hat.event.common.EventPayloadType.SBS,
        data=hat.event.common.SbsData(module=None, type='Array',
                                      data=b'[1, 2, 3]'))),
    (None, None, hat.event.common.EventPayload(
        type=hat.event.common.EventPayloadType.JSON,
        data=[1, 2, 3])),
    ])
@pytest.mark.parametrize("t_from, t_to, source_t_from, source_t_to", [
    (None, None, None, None),
    (hat.event.common.now(), None, None, None),
    (None, hat.event.common.now(), None, None),
    (hat.event.common.now(), hat.event.common.now(), None, None),
    (None, None, hat.event.common.now(), None),
    (None, None, None, hat.event.common.now()),
    ])
@pytest.mark.parametrize("unique_type", [True, False])
@pytest.mark.parametrize("max_results", [None, 2])
@pytest.mark.asyncio
async def test_query_vs_memory_backend(backend_memory_backend,
                                       event_ids, event_types, t_from, t_to,
                                       source_t_from, source_t_to, payload,
                                       unique_type, max_results):

    backend, memory_backend = backend_memory_backend

    q_data = hat.event.server.common.QueryData(
        event_ids=event_ids,
        event_types=event_types,
        t_from=t_from,
        t_to=t_to,
        source_t_from=source_t_from,
        source_t_to=source_t_to,
        payload=payload,
        unique_type=unique_type,
        max_results=max_results)
    assert await backend.query(q_data) == await memory_backend.query(q_data)


@pytest.mark.parametrize("ts_label", ['t_', 'source_t_'])
@pytest.mark.parametrize("time_filter, ts_expected", [
    ({'from': hat.event.common.Timestamp(s=0, us=0)}, [ts0, ts1, ts2]),
    ({'to': hat.event.common.Timestamp(s=0, us=0)}, []),
    ({'to': ts2}, [ts0, ts1, ts2]),
    ({'from': ts2}, [ts2]),
    ({'from': after(ts2)}, []),
    ({'to': ts1}, [ts0, ts1]),
    ({'from': ts1, 'to': ts1}, [ts1]),
    ({'from': ts0, 'to': ts2}, [ts0, ts1, ts2]),
    ({'from': ts2, 'to': ts0}, []),
    ({'from': after(ts1), 'to': after(ts2)}, [ts2]),
    ({'from': after(ts1), 'to': before(ts2)}, []),
    ({'from': after(ts0), 'to': before(ts2)}, [ts1]),
])
@pytest.mark.asyncio
async def test_query_on_time(backend_with_events,
                             ts_label, time_filter, ts_expected):
    backend, reg_events = backend_with_events
    ts_events = {}
    for e in reg_events:
        if e.timestamp in ts_events:
            ts_events[e.timestamp].append(e)
        else:
            ts_events[e.timestamp] = [e]
    query_res_exp = [e for ts in ts_expected for e in ts_events[ts]]
    query_data = hat.event.server.common.QueryData(
        **{ts_label + k: v for k, v in time_filter.items()})
    query_res = await backend.query(query_data)
    assert all(e in query_res_exp for e in query_res)


@pytest.mark.parametrize("order_by",
                         [hat.event.common.OrderBy.TIMESTAMP,
                          hat.event.common.OrderBy.SOURCE_TIMESTAMP])
@pytest.mark.parametrize("order, ts_expected",
                         [(hat.event.common.Order.ASCENDING, ts0),
                          (hat.event.common.Order.DESCENDING, ts2)])
@pytest.mark.asyncio
async def test_order_unique_type(backend_with_events, order_by, order,
                                 ts_expected):
    backend, _ = backend_with_events

    query_res = await backend.query(
        hat.event.server.common.QueryData(unique_type=True,
                                          order_by=order_by,
                                          order=order))
    assert all(e.timestamp == ts_expected for e in query_res)


@pytest.mark.asyncio
async def test_unique_source_ts(backend, backend_events_factory):
    source_ts = hat.event.common.now()
    timestamp_gen = ts_gen(source_ts)
    for i in range(3):
        ts = next(timestamp_gen)
        await backend.register(backend_events_factory(
            timestamp=ts, source_timestamp=source_ts))

    query_res = await backend.query(hat.event.server.common.QueryData(
        unique_type=True,
        order_by=hat.event.common.OrderBy.SOURCE_TIMESTAMP))
    assert all(e.timestamp == ts for e in query_res)


@pytest.mark.asyncio
async def test_persistence(conf_factory, backend_events_factory):
    conf = conf_factory()
    backend = await importlib.import_module(conf['module']).create(conf)
    events = backend_events_factory(timestamp=ts0)
    await backend.register(events)

    await backend.async_close()

    backend = await importlib.import_module(conf['module']).create(conf)
    query_res = await backend.query(hat.event.server.common.QueryData())
    assert all(e in query_res for e in events)
    assert len(query_res) == len(events)

    await backend.async_close()


@pytest.mark.asyncio
async def test_dummy(backend_events_factory):
    conf = {'module': 'hat.event.server.backends.dummy'}
    backend = await importlib.import_module(conf['module']).create(conf)

    backend_events = backend_events_factory(server_id=1)
    await backend.register(backend_events)

    assert not await backend.query(hat.event.server.common.QueryData())

    await backend.async_close()
    assert backend.is_closed
