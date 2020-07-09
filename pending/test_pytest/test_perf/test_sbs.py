import pytest

from hat import sbs
import hat.event.common
import hat.monitor.common


@pytest.mark.parametrize("data_count", [1, 100, 10000])
@pytest.mark.parametrize("data_type,data_factory", [
    ['Array(Boolean)', lambda count: [bool(i % 2)
                                      for i in range(count)]],
    ['Array(Integer)', lambda count: [(-1 if i % 2 else 1) * i
                                      for i in range(count)]],
    ['Array(Float)', lambda count: [(-1 if i % 2 else 1) * i / 100
                                    for i in range(count)]],
    ['Array(String)', lambda count: [str(i) * 10
                                     for i in range(count)]],
    ['Array(Bytes)', lambda count: [(str(i) * 10).encode('utf-8')
                                    for i in range(count)]],
    ['Array(None)', lambda count: [None
                                   for i in range(count)]]
])
def test_builtin(duration, data_count, data_type, data_factory):
    repo = sbs.Repository(f"module Module T = {data_type}")
    data = data_factory(data_count)
    with duration(f"encode {data_type} len={data_count}"):
        result = repo.encode('Module', 'T', data)
    with duration(f"decode {data_type} len={data_count}"):
        repo.decode('Module', 'T', result)


@pytest.mark.parametrize("event_count", [1, 100, 10000])
def test_events(duration, event_count):
    repo = sbs.Repository(hat.event.common.create_sbs_repo(),
                          f"module Module T = Array(HatEvent.Event)")

    data = [hat.event.common.event_to_sbs(hat.event.common.Event(
                event_id=hat.event.common.EventId(1, 12345),
                event_type=['subtype1', 'subtype2', 'subtype3', 'subtype4'],
                timestamp=hat.event.common.now(),
                source_timestamp=hat.event.common.now(),
                payload=hat.event.common.EventPayload(
                    type=hat.event.common.EventPayloadType.JSON,
                    data={'property1': True,
                          'property2': 'abc' * 3,
                          'property3': 12345.23456,
                          'property4': None})))
            for i in range(event_count)]

    with duration(f"encode Array(HatEvent.Event) len={event_count}"):
        result = repo.encode('Module', 'T', data)
    with duration(f"decode Array(HatEvent.Event) len={event_count}"):
        repo.decode('Module', 'T', result)
