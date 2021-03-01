import pytest

from hat.event.server.backends.lmdb import common
import hat.event.server.backends.lmdb.encoder


@pytest.mark.parametrize('event', [
    common.Event(event_id=common.EventId(1, 2),
                 event_type=('a', 'b', 'c'),
                 timestamp=common.now(),
                 source_timestamp=None,
                 payload=None)
])
def test_event(event):
    encoded = hat.event.server.backends.lmdb.encoder.encode_event(event)
    decoded = hat.event.server.backends.lmdb.encoder.decode_event(encoded)
    assert event == decoded


@pytest.mark.parametrize('timestamp_id', [
    (common.now(), 123)
])
def test_timestamp_id(timestamp_id):
    encoded = hat.event.server.backends.lmdb.encoder.encode_timestamp_id(
        timestamp_id)
    decoded = hat.event.server.backends.lmdb.encoder.decode_timestamp_id(
        encoded)
    assert timestamp_id == decoded


@pytest.mark.parametrize('value', [
    'abc'
])
def test_str(value):
    encoded = hat.event.server.backends.lmdb.encoder.encode_str(value)
    decoded = hat.event.server.backends.lmdb.encoder.decode_str(encoded)
    assert value == decoded


@pytest.mark.parametrize('value', [
    [1, 2.3, True, {'a': None}]
])
def test_json(value):
    encoded = hat.event.server.backends.lmdb.encoder.encode_json(value)
    decoded = hat.event.server.backends.lmdb.encoder.decode_json(encoded)
    assert value == decoded


@pytest.mark.parametrize('data', [
    common.SystemData(1, None, None),
    common.SystemData(2, 3, common.now())
])
def test_system_data(data):
    encoded = hat.event.server.backends.lmdb.encoder.encode_system_data(data)
    decoded = hat.event.server.backends.lmdb.encoder.decode_system_data(
        encoded)
    assert data == decoded


@pytest.mark.parametrize('tuple_str', [
    (),
    ('a',),
    ('a', 'b')
])
def test_tuple_str(tuple_str):
    encoded = hat.event.server.backends.lmdb.encoder.encode_tuple_str(
        tuple_str)
    decoded = hat.event.server.backends.lmdb.encoder.decode_tuple_str(
        encoded)
    assert tuple_str == decoded
