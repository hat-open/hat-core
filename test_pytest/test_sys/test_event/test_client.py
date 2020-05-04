import asyncio
import pytest

from hat.event import common
import hat.event.client


@pytest.mark.asyncio
async def test_connect(create_event_server):
    backend_conf = {'module': 'hat.event.server.backends.dummy'}
    modules_conf = []

    with create_event_server(backend_conf, modules_conf) as srv:
        srv.wait_active(5)

        client = await hat.event.client.connect(srv.address)
        assert not client.closed.done()
        await client.async_close()


@pytest.mark.asyncio
async def test_register(create_event_server):
    backend_conf = {'module': 'hat.event.server.backends.dummy'}
    modules_conf = []

    register_event = common.RegisterEvent(
        event_type=['a'],
        source_timestamp=common.now(),
        payload=common.EventPayload(
            type=common.EventPayloadType.BINARY,
            data=b'123'))

    with create_event_server(backend_conf, modules_conf) as srv:
        srv.wait_active(5)

        client = await hat.event.client.connect(srv.address)

        client.register([register_event])
        resp = await client.register_with_response([register_event])

        assert len(resp) == 1
        assert resp[0].event_type == register_event.event_type
        assert resp[0].source_timestamp == register_event.source_timestamp
        assert resp[0].payload == register_event.payload

        assert not client.closed.done()
        await client.async_close()


@pytest.mark.asyncio
async def test_subscribe(create_event_server):
    backend_conf = {'module': 'hat.event.server.backends.dummy'}
    modules_conf = []

    with create_event_server(backend_conf, modules_conf) as srv:
        srv.wait_active(5)

        client = await hat.event.client.connect(srv.address, [['a', '*']])

        client.register([common.RegisterEvent(['a'], None, None)])
        evts = await asyncio.wait_for(client.receive(), 0.1)
        assert evts[0].event_type == ['a']

        client.register([common.RegisterEvent(['b'], None, None)])
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.receive(), 0.1)

        client.register([common.RegisterEvent(['a', 'b', 'c'], None, None)])
        evts = await asyncio.wait_for(client.receive(), 0.1)
        assert evts[0].event_type == ['a', 'b', 'c']

        await client.async_close()


@pytest.mark.asyncio
async def test_query(tmp_path, create_event_server):
    backend_conf = {'module': 'hat.event.server.backends.sqlite',
                    'db_path': str(tmp_path / 'event.db'),
                    'query_pool_size': 1}
    modules_conf = []

    with create_event_server(backend_conf, modules_conf) as srv:
        srv.wait_active(5)

        client = await hat.event.client.connect(srv.address)

        result = await client.query(common.QueryData(event_types=[['*']]))
        assert len(result) == 0

        resp1 = await client.register_with_response(
            [common.RegisterEvent(['a'], common.now(), None)])
        result = await client.query(common.QueryData(event_types=[['*']]))
        assert resp1 == result

        resp2 = await client.register_with_response(
            [common.RegisterEvent(['b'], common.now(), None)])
        result = await client.query(common.QueryData(event_types=[['*']]))
        assert resp2 + resp1 == result

        await client.async_close()


@pytest.mark.parametrize("client_count", [1, 2, 5])
@pytest.mark.asyncio
async def test_multiple_clients(create_event_server, client_count):
    backend_conf = {'module': 'hat.event.server.backends.dummy'}
    modules_conf = []

    with create_event_server(backend_conf, modules_conf) as srv:
        srv.wait_active(5)

        clients = []
        for _ in range(client_count):
            client = await hat.event.client.connect(srv.address, [['*']])
            clients.append(client)

        for i, sender in enumerate(clients):
            client.register(
                [common.RegisterEvent(['a'], None, common.EventPayload(
                    type=common.EventPayloadType.JSON,
                    data=i))])
            for receiver in clients:
                evts = await asyncio.wait_for(receiver.receive(), 1)
                assert evts[0].payload.data == i

        await asyncio.wait([client.async_close() for client in clients])
