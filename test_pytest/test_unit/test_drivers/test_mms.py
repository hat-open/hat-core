import contextlib
import pytest

from hat.drivers import mms


@pytest.fixture
def server_factory(unused_tcp_port_factory):

    @contextlib.asynccontextmanager
    async def factory(connection_cb, request_cb):
        server = await mms.listen(
            connection_cb, request_cb,
            addr=mms.Address('0.0.0.0', unused_tcp_port_factory()))
        try:
            yield server
        finally:
            await server.async_close()

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
async def test_connect(connection_count, server_factory):
    connections = []

    async def connection_cb(connection):
        connections.append(connection)

    async def request_cb(connection, request):
        return mms.Response.StatusResponse(logical=1, physical=1)

    async with server_factory(connection_cb, request_cb) as server:
        address = server.addresses[0]
        for _ in range(connection_count):
            await mms.connect(request_cb, address)

        assert len(connections) == connection_count
