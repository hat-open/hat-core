import pytest

from hat.event import common
import hat.event.client


@pytest.fixture
def server(create_event_server):
    backend_conf = {'module': 'hat.event.server.backends.dummy'}
    modules_conf = []
    with create_event_server(backend_conf, modules_conf) as srv:
        srv.wait_active(1)
        yield srv


@pytest.fixture
async def client(server):
    client = await hat.event.client.connect(server.address)
    yield client
    await client.async_close()


@pytest.mark.asyncio
async def test_dummy(client):
    result = await client.query(common.QueryData(event_types=[('*',)]))
    assert result == []

    resp = await client.register_with_response(
        [common.RegisterEvent(('a',), None, None)])
    assert len(resp) == 1

    result = await client.query(common.QueryData(event_types=[('*',)]))
    assert result == []
