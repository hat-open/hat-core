import collections

import pytest

import hat.event.common
import hat.sbs
import hat.sbs._cserializer
import hat.sbs._pyserializer
import hat.sbs.serializer


serializers = [hat.sbs._cserializer,
               hat.sbs._pyserializer]


@pytest.mark.parametrize("serializer", serializers)
@pytest.mark.parametrize("bulk_encoding", [True, False])
@pytest.mark.parametrize("event_count", [1, 10, 1000, 100000])
def test_event_encoding_duration(monkeypatch, duration,
                                 serializer, event_count, bulk_encoding):
    monkeypatch.setattr(hat.sbs.serializer, '_serializer', serializer)

    events = [
        hat.event.common.event_to_sbs(
            hat.event.common.Event(
                event_id=hat.event.common.EventId(
                    server=0,
                    instance=i),
                event_type=['some', 'event', 'type', str(i)],
                timestamp=hat.event.common.now(),
                source_timestamp=None,
                payload=hat.event.common.EventPayload(
                    type=hat.event.common.EventPayloadType.JSON,
                    data={f'key{j}': f'value{j}' for j in range(10)})))
        for i in range(event_count)]

    if bulk_encoding:
        data = [events]
    else:
        data = [[event] for event in events]

    results = collections.deque()

    with duration(f'{serializer.__name__} encode - '
                  f'event_count: {event_count}; '
                  f'bulk_encoding: {bulk_encoding}'):
        for i in data:
            result = hat.event.common.sbs_repo.encode(
                'HatEvent', 'MsgRegisterReq', i)
            results.append(result)

    with duration(f'{serializer.__name__} decode - '
                  f'event_count: {event_count}; '
                  f'bulk_encoding: {bulk_encoding}'):
        for i in results:
            hat.event.common.sbs_repo.decode(
                'HatEvent', 'MsgRegisterReq', i)
