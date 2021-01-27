import collections
import datetime
import itertools
import math

import pytest

from hat.event.server import common


pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("event_type, query_type, is_match", [
    ([],
     [],
     True),

    ([],
     ['*'],
     True),

    ([],
     ['?'],
     False),

    (['a'],
     [],
     False),

    (['a'],
     ['*'],
     True),

    (['a'],
     ['?'],
     True),

    (['a'],
     ['?', '*'],
     True),

    (['a'],
     ['?', '?'],
     False),

    (['a'],
     ['a'],
     True),

    (['a'],
     ['a', '*'],
     True),

    (['a'],
     ['a', '?'],
     False),

    (['a'],
     ['b'],
     False),

    (['a'],
     ['a', 'b'],
     False),

    (['a', 'b'],
     [],
     False),

    (['a', 'b'],
     ['*'],
     True),

    (['a', 'b'],
     ['?'],
     False),

    (['a', 'b'],
     ['?', '*'],
     True),

    (['a', 'b'],
     ['?', '?'],
     True),

    (['a', 'b'],
     ['?', '?', '*'],
     True),

    (['a', 'b'],
     ['?', '?', '?'],
     False),

    (['a', 'b'],
     ['a'],
     False),

    (['a', 'b'],
     ['a', '*'],
     True),

    (['a', 'b'],
     ['a', '?'],
     True),

    (['a', 'b'],
     ['a', '?', '*'],
     True),

    (['a', 'b'],
     ['a', '?', '?'],
     False),

    (['a', 'b'],
     ['?', 'b'],
     True),

    (['a', 'b'],
     ['?', 'b', '*'],
     True),

    (['a', 'b'],
     ['?', 'b', '?'],
     False),

    (['a', 'b'],
     ['b', 'a'],
     False),

    (['a', 'b'],
     ['a', 'b', 'c'],
     False)
])
def test_matches_query_type(event_type, query_type, is_match):
    result = common.matches_query_type(event_type, query_type)
    assert result is is_match


@pytest.mark.parametrize("t1, t2", itertools.permutations([
    common.Timestamp(0, 0),
    common.Timestamp(0, 1),
    common.Timestamp(1, 0),
    common.Timestamp(1, 1),
    common.Timestamp(0, -1),
    common.Timestamp(-1, 0),
    common.Timestamp(-1, -1),
    common.Timestamp(-1, 999_999)
], r=2))
def test_timestamp(t1, t2):
    us1 = 1_000_000 * t1.s + t1.us
    us2 = 1_000_000 * t2.s + t2.us

    assert (t1 == t2) is (us1 == us2)
    assert (t1 != t2) is (us1 != us2)
    assert (t1 < t2) is (us1 < us2)
    assert (t1 > t2) is (us1 > us2)
    assert (t1 <= t2) is (us1 <= us2)
    assert (t1 >= t2) is (us1 >= us2)
    assert (hash(t1) == hash(t2)) is (us1 == us2)

    with pytest.raises(TypeError):
        t1 < None

    with pytest.raises(TypeError):
        t1 > 'abc'

    assert t1 != 123


@pytest.mark.parametrize("t, t_bytes", [
    (common.Timestamp(0, 0),
     b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'),

    (common.Timestamp(2_145_916_800, 99_999),
     b'\x00\x00\x00\x00\x7f\xe8\x17\x80\x00\x01\x86\x9f'),

    (common.Timestamp(12_321, 99_999),
     b'\x00\x00\x00\x00\x00\x00\x30\x21\x00\x01\x86\x9f')
])
def test_timestamp_bytes(t, t_bytes):
    assert common.timestamp_to_bytes(t) == t_bytes
    assert common.timestamp_from_bytes(t_bytes) == t


@pytest.mark.parametrize("t, t_float", [
    (common.Timestamp(0, 0),
     0.0),

    (common.Timestamp(1, 0),
     1.0),

    (common.Timestamp(1_000, 10_000),
     1_000.01),

    (common.Timestamp(-473_385_600, 123),
     -473_385_600 + 123 * 1e-6),

    (common.Timestamp(473_385_600, 123),
     473_385_600 + 123 * 1e-6),

    (common.Timestamp(4_099_680_000, 123),
     4_099_680_000 + 123 * 1e-6),

    (common.Timestamp(409_968, 999_999),
     409_968 + 999_999 * 1e-6),

    (common.Timestamp(409_968, 999_999),
     409_968 + 9_999_994 * 1e-7),

    (common.Timestamp(409_969, 0),
     409_968 + 9_999_996 * 1e-7),

    (common.Timestamp(409_969, 0),
     409_968 + 9_999_999 * 1e-7),

    (common.Timestamp(-409_969, 1),
     -409_968 - 9_999_994 * 1e-7),

    (common.Timestamp(-409_969, 0),
     -409_968 - 9_999_996 * 1e-7),

    (common.Timestamp(-409_968, 0),
     -409_968 - 4 * 1e-7),

    (common.Timestamp(-409_969, 999_999),
     -409_968 - 6 * 1e-7)
])
def test_timestamp_float(t, t_float):
    assert math.isclose(common.timestamp_to_float(t), t_float, abs_tol=1e-9)
    assert common.timestamp_from_float(t_float) == t


@pytest.mark.parametrize("t, t_dt", [
    (common.Timestamp(-2_208_988_800, 999_999),
     datetime.datetime(1900, 1, 1, 0, 0, 0, 999_999,
                       tzinfo=datetime.timezone.utc)),

    (common.Timestamp(0, 0),
     datetime.datetime(1970, 1, 1, 0, 0, 0, 0,
                       tzinfo=datetime.timezone.utc)),

    (common.Timestamp(0, 123),
     datetime.datetime(1970, 1, 1, 0, 0, 0, 123,
                       tzinfo=datetime.timezone.utc)),

    (common.Timestamp(2_145_916_800, 99_999),
     datetime.datetime(2038, 1, 1, 0, 0, 0, 99_999,
                       tzinfo=datetime.timezone.utc)),

    (common.Timestamp(4_133_980_799, 1),
     datetime.datetime(2100, 12, 31, 23, 59, 59, 1,
                       tzinfo=datetime.timezone.utc))
])
def test_timestamp_datetime(t, t_dt):
    assert common.timestamp_to_datetime(t) == t_dt
    assert common.timestamp_from_datetime(t_dt) == t
    assert common.timestamp_from_datetime(t_dt.replace(tzinfo=None)) == t


@pytest.mark.parametrize("t", [
    common.Timestamp(-2_208_988_800, 999_999),
    common.Timestamp(0, 0),
    common.Timestamp(0, 123),
    common.Timestamp(2_145_916_800, 99_999),
    common.Timestamp(4_133_980_799, 1)
])
def test_timestamp_sbs(t):
    encoded = common.timestamp_to_sbs(t)
    decoded = common.timestamp_from_sbs(encoded)
    assert decoded == t


def test_now():
    previous_dt = None

    for _ in range(10):
        now_dt = common.timestamp_to_datetime(common.now())
        delta = datetime.datetime.now(datetime.timezone.utc) - now_dt

        assert delta < datetime.timedelta(seconds=1)
        if previous_dt is not None:
            assert now_dt >= previous_dt

        previous_dt = now_dt


@pytest.mark.parametrize("event", [
    common.Event(
        event_id=common.EventId(0, 0),
        event_type=['a'],
        timestamp=common.now(),
        source_timestamp=None,
        payload=None),

    common.Event(
        event_id=common.EventId(0, 0),
        event_type=['a'],
        timestamp=common.now(),
        source_timestamp=common.now(),
        payload=common.EventPayload(
            type=common.EventPayloadType.BINARY,
            data=b'123')),

    common.Event(
        event_id=common.EventId(123, 456),
        event_type=['a', 'b', 'c'],
        timestamp=common.now(),
        source_timestamp=common.now(),
        payload=common.EventPayload(
            type=common.EventPayloadType.JSON,
            data=None)),

    common.Event(
        event_id=common.EventId(123, 456),
        event_type=['a', 'b', 'c'],
        timestamp=common.now(),
        source_timestamp=common.now(),
        payload=common.EventPayload(
            type=common.EventPayloadType.JSON,
            data=[{}, None, [], True, False, 1, 2.5, "123"]))
])
def test_event_sbs(event):
    encoded = common.event_to_sbs(event)
    decoded = common.event_from_sbs(encoded)
    assert decoded == event


@pytest.mark.parametrize("register_event", [
    common.RegisterEvent(
        event_type=['a'],
        source_timestamp=None,
        payload=None),

    common.RegisterEvent(
        event_type=['a'],
        source_timestamp=common.now(),
        payload=common.EventPayload(
            type=common.EventPayloadType.SBS,
            data=common.SbsData(None, 'Integer', 123))),

    common.RegisterEvent(
        event_type=['a'],
        source_timestamp=common.now(),
        payload=common.EventPayload(
            type=common.EventPayloadType.BINARY,
            data=b'123')),

    common.RegisterEvent(
        event_type=['a', 'b', 'c'],
        source_timestamp=common.now(),
        payload=common.EventPayload(
            type=common.EventPayloadType.JSON,
            data=None)),

    common.RegisterEvent(
        event_type=['a', 'b', 'c'],
        source_timestamp=common.now(),
        payload=common.EventPayload(
            type=common.EventPayloadType.JSON,
            data=[{}, None, [], True, False, 1, 2.5, "123"]))
])
def test_register_event_sbs(register_event):
    encoded = common.register_event_to_sbs(register_event)
    decoded = common.register_event_from_sbs(encoded)
    assert decoded == register_event


@pytest.mark.parametrize("query", [
    common.QueryData()
])
def test_query_sbs(query):
    encoded = common.query_to_sbs(query)
    decoded = common.query_from_sbs(encoded)
    assert decoded == query


@pytest.mark.parametrize("event_type", [
    [],
    [''],
    ['a'],
    ['b'],
    ['a', 'a'],
    ['a', 'b'],
    ['a', 'b', 'c']])
def test_subscription_registry(event_type):
    subscriptions = [
        [],
        ['*'],
        ['?'],
        [''],
        ['?', '*'],
        ['?', '?'],
        ['a'],
        ['a', '*'],
        ['a', '?'],
        ['b'],
        ['a', 'b'],
        ['?', '?', '*'],
        ['?', '?', '?'],
        ['a', '?', '*'],
        ['a', '?', '?'],
        ['?', 'b'],
        ['?', 'b', '*'],
        ['?', 'b', '?'],
        ['b', 'a'],
        ['a', 'b', 'c']]
    value_sub_pairs = collections.deque()

    registry = common.SubscriptionRegistry()
    assert registry.find(event_type) == set()

    for value, sub in enumerate(subscriptions):
        value_sub_pairs.append((value, sub))
        registry.add(value, sub)

        assert registry.find(event_type) == {
            value for value, sub in value_sub_pairs
            if common.matches_query_type(event_type, sub)}

    for _ in range(len(value_sub_pairs)):
        value, sub = value_sub_pairs.popleft()
        registry.remove(value)

        assert registry.find(event_type) == {
            value for value, sub in value_sub_pairs
            if common.matches_query_type(event_type, sub)}

    assert registry.find(event_type) == set()


class MockEventTypeRegistryStorage(common.EventTypeRegistryStorage):

    def __init__(self, mappings):
        self._mappings = mappings

    @property
    def mappings(self):
        return self._mappings

    async def get_event_type_mappings(self):
        return self._mappings

    async def add_event_type_mappings(self, mappings):
        self._mappings.update(mappings)


async def test_event_type_registry_get_event_type():
    storage = MockEventTypeRegistryStorage({})
    registry = await common.create_event_type_registry(storage)
    with pytest.raises(Exception):
        registry.get_event_type(0)
    with pytest.raises(Exception):
        registry.get_event_type(1)

    storage = MockEventTypeRegistryStorage({1: ['a', 'b', 'c'],
                                            5: ['x', 'y', 'z']})
    registry = await common.create_event_type_registry(storage)
    assert len(storage.mappings) == 6
    assert registry.get_event_type(1) == ['a', 'b', 'c']
    assert registry.get_event_type(5) == ['x', 'y', 'z']
    with pytest.raises(Exception):
        registry.get_event_type(3)


async def test_event_type_registry_get_identifiers():
    storage = MockEventTypeRegistryStorage({})
    registry = await common.create_event_type_registry(storage)

    assert len(storage.mappings) == 0

    ids = await registry.get_identifiers([['a'], ['b', 'c']])
    assert len(storage.mappings) == 3
    assert len(ids) == 2
    for i in ids:
        assert isinstance(i, int)

    ids = await registry.get_identifiers([['b']])
    assert len(storage.mappings) == 3
    assert len(ids) == 1
    assert isinstance(ids[0], int)

    event_types = [['a', 'b', 'c'],
                   ['x', 'y', 'z']]
    ids = await registry.get_identifiers(event_types)
    assert len(event_types) == len(ids)
    for event_type, event_type_id in zip(event_types, ids):
        assert registry.get_event_type(event_type_id) == event_type


async def test_event_type_registry_query_identifiers():
    storage = MockEventTypeRegistryStorage({1: ['a'],
                                            2: ['a', 'b'],
                                            3: ['a', 'c'],
                                            4: ['a', 'b', 'd']})
    registry = await common.create_event_type_registry(storage)

    ids = registry.query_identifiers([[]])
    assert len(ids) == 0

    ids = registry.query_identifiers([['*']])
    assert ids == {1, 2, 3, 4}

    ids = registry.query_identifiers([['a', '*']])
    assert ids == {1, 2, 3, 4}

    ids = registry.query_identifiers([['a', 'b', '*']])
    assert ids == {2, 4}

    ids = registry.query_identifiers([['a', '?']])
    assert ids == {2, 3}

    ids = registry.query_identifiers([['a', '?', '?']])
    assert ids == {4}

    ids = registry.query_identifiers([['a', '?', 'd']])
    assert ids == {4}

    ids = registry.query_identifiers([['a', '?', 'a']])
    assert len(ids) == 0

    ids = registry.query_identifiers([['a', '?', '*']])
    assert ids == {2, 3, 4}
