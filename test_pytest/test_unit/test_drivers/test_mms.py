import asyncio
import contextlib
import pytest

from hat.drivers import mms


@pytest.fixture
def server_factory(unused_tcp_port_factory):

    @contextlib.asynccontextmanager
    async def factory(connection_cb, request_cb):
        connections = []

        async def on_connection(conn):
            connections.append(conn)
            await connection_cb(conn)

        server = await mms.listen(
            on_connection, request_cb,
            addr=mms.Address('0.0.0.0', unused_tcp_port_factory()))
        try:
            yield server
        finally:
            await asyncio.wait([server.async_close(),
                                *(conn.async_close() for conn in connections)])

    return factory


@pytest.mark.asyncio
async def test_listen(server_factory):

    async def connection_cb(connection):
        pass

    async def request_cb(connection, request):
        return mms.Response.StatusResponse(logical=1, physical=1)

    async with server_factory(connection_cb, request_cb) as server:
        assert len(server.addresses) == 1


@pytest.mark.parametrize("connection_count", [1, 2, 10])
@pytest.mark.asyncio
async def test_can_connect(connection_count, server_factory):
    server_connections = []
    client_connections = []

    async def connection_cb(connection):
        server_connections.append(connection)

    async def request_cb(connection, request):
        return mms.Response.StatusResponse(logical=1, physical=1)

    async with server_factory(connection_cb, request_cb) as server:
        address = server.addresses[0]
        for _ in range(connection_count):
            conn = await mms.connect(request_cb, address)
            client_connections.append(conn)

        assert len(server_connections) == connection_count

    await asyncio.wait([conn.async_close() for conn in client_connections])


@pytest.mark.asyncio
@pytest.mark.timeout(2)
async def test_request_response(server_factory):
    request = mms.StatusRequest()
    response = mms.StatusResponse(logical=1, physical=1)
    requests_received = []

    async def connection_cb(_):
        pass

    async def server_req_cb(connection, request):
        requests_received.append(request)
        return response

    async def client_req_cb(connection, request):
        pass

    async with server_factory(connection_cb, server_req_cb) as server:
        address = server.addresses[0]
        conn = await mms.connect(client_req_cb, address)
        received_status = await conn.send_confirmed(request)

    assert len(requests_received) == 1
    assert requests_received == [request]
    assert received_status == response

    await conn.async_close()


@pytest.mark.asyncio
async def test_unconfirmed(server_factory):
    unconfirmed = mms.UnsolicitedStatusUnconfirmed(logical=1, physical=1)

    async def connection_cb(connection):
        connection.send_unconfirmed(unconfirmed)

    async def server_req_cb(connection, request):
        pass

    async def client_req_cb(connection, request):
        pass

    async with server_factory(connection_cb, server_req_cb) as server:
        address = server.addresses[0]
        conn = await mms.connect(client_req_cb, address)
        received_unconfirmed = await conn.receive_unconfirmed()

    assert unconfirmed == received_unconfirmed
