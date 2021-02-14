import asyncio

import pytest

from hat import util
from hat.drivers import tpkt


pytestmark = pytest.mark.asyncio


@pytest.fixture
def addr():
    return tpkt.Address('127.0.0.1', util.get_unused_tcp_port())


async def test_connect_listen(addr):
    conn1_future = asyncio.Future()
    srv = await tpkt.listen(conn1_future.set_result, addr)
    assert srv.addresses == [addr]

    conn2 = await tpkt.connect(addr)
    conn1 = await conn1_future

    assert not srv.is_closed
    assert not conn1.is_closed
    assert not conn2.is_closed

    assert conn1.info.local_addr == addr
    assert conn1.info.local_addr == conn2.info.remote_addr
    assert conn1.info.remote_addr == conn2.info.local_addr

    await asyncio.gather(conn1.async_close(), conn2.async_close(),
                         srv.async_close())

    assert srv.is_closed
    assert conn1.is_closed
    assert conn2.is_closed


async def test_read_write(addr):
    conn1_future = asyncio.Future()
    srv = await tpkt.listen(conn1_future.set_result, addr)
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


async def test_invalid_connection_cb(addr):
    srv = await tpkt.listen(None, addr)
    conn = await tpkt.connect(addr)
    await conn.async_close()
    await srv.async_close()


async def test_invalid_data(addr):
    conn_future = asyncio.Future()
    srv = await tpkt.listen(conn_future.set_result, addr)
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
