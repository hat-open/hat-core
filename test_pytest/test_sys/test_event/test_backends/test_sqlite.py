import pytest

from hat.event import common
import hat.event.client


@pytest.fixture
def server(tmp_path, create_event_server):
    backend_conf = {'module': 'hat.event.server.backends.sqlite',
                    'db_path': str(tmp_path / 'event.db'),
                    'query_pool_size': 5}
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
async def test_empty(client):
    result = await client.query(common.QueryData(event_types=[('*',)]))
    assert len(result) == 1
    assert result[0].event_type == ('event', 'communication', 'connected')


@pytest.mark.parametrize("register_count", [1, 2, 5])
@pytest.mark.parametrize("register_size", [1, 2, 5])
@pytest.mark.asyncio
async def test_multiple_writes(client, register_count, register_size):
    for i in range(register_count):
        resp = await client.register_with_response(
            [common.RegisterEvent(('a',), None, None)
             for _ in range(register_size)])
        assert len(resp) == register_size

        result = await client.query(common.QueryData(event_types=[('a',)]))
        assert len(result) == (i + 1) * register_size


@pytest.mark.parametrize("payload_type,payload_data", [
    [common.EventPayloadType.BINARY, b'123'],
    [common.EventPayloadType.JSON, {'a': [1, '2', None, True, False]}],
    [common.EventPayloadType.SBS, common.SbsData('a', 'b', b'xyz')]
])
@pytest.mark.asyncio
async def test_payload(client, payload_type, payload_data):
    resp = await client.register_with_response([common.RegisterEvent(
        ('a',), None, common.EventPayload(payload_type, payload_data))])
    result = await client.query(common.QueryData(event_types=[('a',)]))

    assert resp == result
    assert len(result) == 1
    assert result[0].payload == common.EventPayload(payload_type, payload_data)
