import pytest

from hat.event.server import common
import hat.event.server.backends.dummy


pytestmark = pytest.mark.asyncio


async def test_create():
    conf = {'module': 'hat.event.server.backends.dummy'}
    backend = await hat.event.server.backends.dummy.create(conf)

    assert isinstance(backend, common.Backend)
    assert backend.is_open

    await backend.async_close()
    assert backend.is_closed


@pytest.mark.parametrize("server_id", [0, 1, 5, 10])
async def test_get_last_event_id(server_id):
    conf = {'module': 'hat.event.server.backends.dummy'}
    backend = await hat.event.server.backends.dummy.create(conf)

    event_id = await backend.get_last_event_id(server_id)
    assert event_id == common.EventId(server_id, 0)

    await backend.async_close()


@pytest.mark.parametrize("event_count", [0, 1, 5, 10])
async def test_register(event_count):
    events = [
        hat.event.common.Event(
            event_id=hat.event.common.EventId(server=0, instance=i),
            event_type=(),
            timestamp=common.now(),
            source_timestamp=None,
            payload=None)
        for i in range(event_count)]

    conf = {'module': 'hat.event.server.backends.dummy'}
    backend = await hat.event.server.backends.dummy.create(conf)

    result = await backend.register(events)
    assert result == events

    await backend.async_close()


@pytest.mark.parametrize("query_data", [
    common.QueryData()
])
async def test_query(query_data):
    conf = {'module': 'hat.event.server.backends.dummy'}
    backend = await hat.event.server.backends.dummy.create(conf)

    result = await backend.query(query_data)
    assert result == []

    await backend.async_close()
