import asyncio

import pytest

from hat import util
from hat import aio
from hat.drivers import tcp


pytestmark = pytest.mark.asyncio


@pytest.fixture
def addr():
    return tcp.Address('127.0.0.1', util.get_unused_tcp_port())


async def test_connect_listen(addr):
    with pytest.raises(ConnectionError):
        await tcp.connect(addr)

    conn_queue = aio.Queue()
    srv = await tcp.listen(conn_queue.put_nowait, addr)
    conn1 = await tcp.connect(addr)
    conn2 = await conn_queue.get()

    assert srv.is_open
    assert conn1.is_open
    assert conn2.is_open

    assert srv.addresses == [addr]
    assert conn1.info.local_addr == conn2.info.remote_addr
    assert conn1.info.remote_addr == conn2.info.local_addr

    await conn1.async_close()
    await conn2.async_close()
    await srv.async_close()


async def test_read(addr):
    conn_queue = aio.Queue()
    srv = await tcp.listen(conn_queue.put_nowait, addr)
    conn1 = await tcp.connect(addr)
    conn2 = await conn_queue.get()

    data = b'123'

    result = await conn1.read(0)
    assert result == b''

    conn1.write(data)
    await conn1.drain()
    result = await conn2.read(len(data))
    assert result == data

    conn2.write(data)
    result = await conn1.read(len(data) - 1)
    assert result == data[:-1]
    result = await conn1.read(1)
    assert result == data[-1:]

    conn2.write(data)
    result = await conn1.read(len(data) + 1)
    assert result == data

    conn2.write(data)
    await conn2.async_close()
    result = await conn1.read()
    assert result == data

    with pytest.raises(ConnectionError):
        await conn1.read()
    with pytest.raises(ConnectionError):
        await conn2.read()

    await conn1.async_close()
    await srv.async_close()


async def test_readexactly(addr):
    conn_queue = aio.Queue()
    srv = await tcp.listen(conn_queue.put_nowait, addr)
    conn1 = await tcp.connect(addr)
    conn2 = await conn_queue.get()

    data = b'123'

    result = await conn1.readexactly(0)
    assert result == b''

    conn1.write(data)
    result = await conn2.readexactly(len(data))
    assert result == data

    conn2.write(data)
    result = await conn1.readexactly(len(data) - 1)
    assert result == data[:-1]
    result = await conn1.readexactly(1)
    assert result == data[-1:]

    conn2.write(data)
    await conn2.async_close()
    with pytest.raises(ConnectionError):
        await conn1.readexactly(len(data) + 1)
    with pytest.raises(ConnectionError):
        await conn1.readexactly(1)

    await conn1.async_close()
    await srv.async_close()


@pytest.mark.parametrize("bind_connections", [True, False])
@pytest.mark.parametrize("conn_count", [1, 2, 5])
async def test_bind_connections(addr, bind_connections, conn_count):
    conn_queue = aio.Queue()
    srv = await tcp.listen(conn_queue.put_nowait, addr,
                           bind_connections=bind_connections)

    conns = []
    for _ in range(conn_count):
        conn1 = await tcp.connect(addr)
        conn2 = await conn_queue.get()

        conns.append((conn1, conn2))

    for conn1, conn2 in conns:
        assert conn1.is_open
        assert conn2.is_open

    await srv.async_close()

    for conn1, conn2 in conns:
        if bind_connections:
            with pytest.raises(ConnectionError):
                await conn1.read()
            assert not conn1.is_open
            assert not conn2.is_open

        else:
            assert conn1.is_open
            assert conn2.is_open

        await conn1.async_close()
        await conn2.async_close()


async def test_example_docs():
    addr = tcp.Address('127.0.0.1', util.get_unused_tcp_port())

    conn2_future = asyncio.Future()
    srv = await tcp.listen(conn2_future.set_result, addr)
    conn1 = await tcp.connect(addr)
    conn2 = await conn2_future

    # send from conn1 to conn2
    data = b'123'
    conn1.write(data)
    result = await conn2.readexactly(len(data))
    assert result == data

    # send from conn2 to conn1
    data = b'321'
    conn2.write(data)
    result = await conn1.readexactly(len(data))
    assert result == data

    await conn1.async_close()
    await conn2.async_close()
    await srv.async_close()
