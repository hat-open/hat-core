import pytest
import collections
import datetime as dt
import itertools
import math

import hat.event.common as common


@pytest.mark.parametrize("event_type,query_type,is_match", [
    ([], [], True),
    ([], ['*'], True),
    ([], ['?'], False),
    (['a'], [], False),
    (['a'], ['*'], True),
    (['a'], ['?'], True),
    (['a'], ['?', '*'], True),
    (['a'], ['?', '?'], False),
    (['a'], ['a'], True),
    (['a'], ['a', '*'], True),
    (['a'], ['a', '?'], False),
    (['a'], ['b'], False),
    (['a'], ['a', 'b'], False),
    (['a', 'b'], [], False),
    (['a', 'b'], ['*'], True),
    (['a', 'b'], ['?'], False),
    (['a', 'b'], ['?', '*'], True),
    (['a', 'b'], ['?', '?'], True),
    (['a', 'b'], ['?', '?', '*'], True),
    (['a', 'b'], ['?', '?', '?'], False),
    (['a', 'b'], ['a'], False),
    (['a', 'b'], ['a', '*'], True),
    (['a', 'b'], ['a', '?'], True),
    (['a', 'b'], ['a', '?', '*'], True),
    (['a', 'b'], ['a', '?', '?'], False),
    (['a', 'b'], ['?', 'b'], True),
    (['a', 'b'], ['?', 'b', '*'], True),
    (['a', 'b'], ['?', 'b', '?'], False),
    (['a', 'b'], ['b', 'a'], False),
    (['a', 'b'], ['a', 'b', 'c'], False)])
def test_matches_query_type(event_type, query_type, is_match):
    assert common.matches_query_type(event_type, query_type) == is_match


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


@pytest.mark.parametrize("pair1,pair2", itertools.permutations([
    (0, 0),
    (0, 1),
    (1, 0),
    (1, 1),
    (0, -1),
    (-1, 0),
    (-1, -1),
    (-1, 999_999),
    (0, 1_000_001)], r=2))
def test_timestamp(pair1, pair2):
    us1 = 1_000_000 * pair1[0] + pair1[1]
    us2 = 1_000_000 * pair2[0] + pair2[1]

    t1 = common.Timestamp(s=pair1[0], us=pair1[1])
    t2 = common.Timestamp(s=pair2[0], us=pair2[1])

    assert (t1 == t2) == (us1 == us2)
    assert (t1 != t2) == (us1 != us2)
    assert (t1 < t2) == (us1 < us2)
    assert (t1 > t2) == (us1 > us2)
    assert (t1 <= t2) == (us1 <= us2)
    assert (t1 >= t2) == (us1 >= us2)


timestamp_bytes_pairs = [
    (common.Timestamp(0, 0),
     b'\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'),
    (common.Timestamp(2_145_916_800, 99_999),
     b'\x80\x00\x00\x00\x7f\xe8\x17\x80\x00\x01\x86\x9f'),
    (common.Timestamp(12_321, 99_999),
     b'\x80\x00\x00\x00\x00\x00\x30\x21\x00\x01\x86\x9f')]


@pytest.mark.parametrize("timestamp,bytes", timestamp_bytes_pairs)
def test_timestamp_to_bytes(timestamp, bytes):
    assert common.timestamp_to_bytes(timestamp) == bytes


@pytest.mark.parametrize("timestamp,bytes", timestamp_bytes_pairs)
def test_timestamp_from_bytes(timestamp, bytes):
    assert common.timestamp_from_bytes(bytes) == timestamp


@pytest.mark.parametrize("timestamp,float", [
    (common.Timestamp(0, 0), 0.0),
    (common.Timestamp(1, 0), 1.0),
    (common.Timestamp(1_000, 10_000), 1_000.01),
    (common.Timestamp(-473_385_600, 123), -473_385_600 + 123 * 1e-6),
    (common.Timestamp(473_385_600, 123), 473_385_600 + 123 * 1e-6),
    (common.Timestamp(4_099_680_000, 123), 4_099_680_000 + 123 * 1e-6),
    (common.Timestamp(409_968, 999_999), 409_968 + 999_999 * 1e-6)])
def test_timestamp_to_float(timestamp, float):
    assert math.isclose(common.timestamp_to_float(timestamp), float,
                        abs_tol=1e-9)


@pytest.mark.parametrize("timestamp,float", [
    (common.Timestamp(0, 0), 0.0),
    (common.Timestamp(1, 0), 1.0),
    (common.Timestamp(1_000, 10_000), 1_000.01),
    (common.Timestamp(-473_385_600, 123), -473_385_600 + 123 * 1e-6),
    (common.Timestamp(473_385_600, 123), 473_385_600 + 123 * 1e-6),
    (common.Timestamp(4_099_680_000, 123), 4_099_680_000 + 123 * 1e-6),
    (common.Timestamp(409_968, 999_999), 409_968 + 999_999 * 1e-6),
    (common.Timestamp(409_968, 999_999), 409_968 + 9_999_994 * 1e-7),
    (common.Timestamp(409_969, 0), 409_968 + 9_999_996 * 1e-7),
    (common.Timestamp(409_969, 0), 409_968 + 9_999_999 * 1e-7),
    (common.Timestamp(-409_969, 1), -409_968 - 9_999_994 * 1e-7),
    (common.Timestamp(-409_969, 0), -409_968 - 9_999_996 * 1e-7),
    (common.Timestamp(-409_968, 0), -409_968 - 4 * 1e-7),
    (common.Timestamp(-409_969, 999_999), -409_968 - 6 * 1e-7)])
def test_timestamp_from_float(timestamp, float):
    assert common.timestamp_from_float(float) == timestamp


timestamp_datetime_pairs = [
    (common.Timestamp(-2_208_988_800, 999_999),
     dt.datetime(1900, 1, 1, 0, 0, 0, 999_999, tzinfo=dt.timezone.utc)),
    (common.Timestamp(0, 0),
     dt.datetime(1970, 1, 1, 0, 0, 0, 0, tzinfo=dt.timezone.utc)),
    (common.Timestamp(0, 123),
     dt.datetime(1970, 1, 1, 0, 0, 0, 123, tzinfo=dt.timezone.utc)),
    (common.Timestamp(2_145_916_800, 99_999),
     dt.datetime(2038, 1, 1, 0, 0, 0, 99_999, tzinfo=dt.timezone.utc)),
    (common.Timestamp(4_133_980_799, 1),
     dt.datetime(2100, 12, 31, 23, 59, 59, 1, tzinfo=dt.timezone.utc))]


@pytest.mark.parametrize("timestamp,datetime", timestamp_datetime_pairs)
def test_timestamp_to_datetime(timestamp, datetime):
    assert common.timestamp_to_datetime(timestamp) == datetime


@pytest.mark.parametrize("timestamp,datetime", timestamp_datetime_pairs)
def test_timestamp_from_datetime(timestamp, datetime):
    assert common.timestamp_from_datetime(datetime) == timestamp


def test_now():
    previous_dt = None

    for _ in range(10):
        now_dt = common.timestamp_to_datetime(common.now())
        assert dt.datetime.now(
            dt.timezone.utc) - now_dt < dt.timedelta(seconds=1)

        if previous_dt is not None:
            assert now_dt >= previous_dt

        previous_dt = now_dt
