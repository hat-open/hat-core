import pytest

from hat.event import common
import hat.event.client


@pytest.fixture
def create_server(tmp_path, create_event_server):

    def create_server(query_pool_size):
        backend_conf = {'module': 'hat.event.server.backends.sqlite',
                        'db_path': str(tmp_path / 'event.db'),
                        'query_pool_size': query_pool_size}
        srv = create_event_server(backend_conf, [])
        srv.wait_active(1)
        return srv

    return create_server


@pytest.fixture
def create_client(sbs_repo):

    async def create_client(address):
        return await hat.event.client.connect(sbs_repo, address)

    return create_client


@pytest.mark.asyncio
async def test_query_empty(duration, create_server, create_client):
    with create_server(1) as server:
        client = await create_client(server.address)

        with duration("query empty database with empty QueryData "
                      "(fist time)"):
            await client.query(common.QueryData())

        with duration("query empty database with empty QueryData "
                      "(second time)"):
            await client.query(common.QueryData())

        with duration("query empty database for all event types"):
            await client.query(common.QueryData(event_types=[['*']]))

        await client.async_close()


@pytest.mark.parametrize("event_count", [1, 10, 100, 1000, 10000])
@pytest.mark.asyncio
async def test_register_simple(duration, create_server, create_client,
                               event_count):
    with create_server(1) as server:
        client = await create_client(server.address)
        register_events = [common.RegisterEvent(['a'], None, None)
                           for _ in range(event_count)]

        message = f"bulk register {event_count} minimal events"

        with duration(f"{message} (first time)"):
            await client.register_with_response(register_events)

        with duration(f"{message} (second time)"):
            await client.register_with_response(register_events)

        await client.async_close()
