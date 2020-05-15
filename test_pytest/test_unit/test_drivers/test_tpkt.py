import pytest
import asyncio

from hat.drivers import tpkt


@pytest.fixture
def addr(unused_tcp_port):
    return tpkt.Address('127.0.0.1', unused_tcp_port)


@pytest.mark.asyncio
async def test_connect_listen(addr):
    conn1_future = asyncio.Future()
    srv = await tpkt.listen(lambda conn: conn1_future.set_result(conn), addr)
    assert srv.addresses == [addr]

    conn2 = await tpkt.connect(addr)
    conn1 = await conn1_future

    assert not srv.closed.done()
    assert not conn1.closed.done()
    assert not conn2.closed.done()

    assert conn1.info.local_addr == addr
    assert conn1.info.local_addr == conn2.info.remote_addr
    assert conn1.info.remote_addr == conn2.info.local_addr

    await asyncio.gather(conn1.async_close(), conn2.async_close(),
                         srv.async_close())

    assert srv.closed.done()
    assert conn1.closed.done()
    assert conn2.closed.done()


@pytest.mark.asyncio
async def test_read_write(addr):
    conn1_future = asyncio.Future()
    srv = await tpkt.listen(lambda conn: conn1_future.set_result(conn), addr)
    conn2 = await tpkt.connect(addr)
    conn1 = await conn1_future

    write_data = b'12345'
    conn1.write(write_data)
    read_data = await conn2.read()
    assert write_data == read_data

    await conn1.async_close()
    with pytest.raises(Exception):
        await conn2.read()
    await conn2.async_close()
    await srv.async_close()


@pytest.mark.asyncio
async def test_invalid_connection_cb(addr):
    srv = await tpkt.listen(None, addr)
    conn = await tpkt.connect(addr)
    await conn.async_close()
    await srv.async_close()


@pytest.mark.asyncio
async def test_invalid_data(addr):
    conn_future = asyncio.Future()
    srv = await tpkt.listen(lambda conn: conn_future.set_result(conn), addr)
    reader, writer = await asyncio.open_connection(addr.host, addr.port)
    conn = await conn_future

    with pytest.raises(Exception):
        conn.write(b'')
    with pytest.raises(Exception):
        conn.write(bytes([0] * 0xffff))

    writer.write(b'\x00\x00\x00\x00')
    with pytest.raises(Exception):
        await conn.read()

    writer.write(b'\x03\x00\x00\x00')
    with pytest.raises(Exception):
        await conn.read()

    await conn.async_close()
    await srv.async_close()


@pytest.mark.asyncio
async def test_invalid_connect_cleanup(addr, monkeypatch):

    class ConnectionMock:

        def __init__(self):
            raise Exception()

    with monkeypatch.context() as ctx:
        ctx.setattr(tpkt, 'Connection', ConnectionMock)
        srv = await tpkt.listen(None, addr)

        with pytest.raises(Exception):
            await tpkt.connect(addr)

        await srv.async_close()
