import asyncio

import pytest

from hat import util
from hat.drivers import cotp


pytestmark = pytest.mark.asyncio


@pytest.fixture
def addr():
    return cotp.Address('127.0.0.1', util.get_unused_tcp_port())


async def test_example_docs():
    addr = cotp.Address('127.0.0.1', util.get_unused_tcp_port())

    conn2_future = asyncio.Future()
    srv = await cotp.listen(conn2_future.set_result, addr)
    conn1 = await cotp.connect(addr)
    conn2 = await conn2_future

    # send from conn1 to conn2
    data = b'123'
    conn1.write(data)
    result = await conn2.read()
    assert result == data

    # send from conn2 to conn1
    data = b'321'
    conn2.write(data)
    result = await conn1.read()
    assert result == data

    await conn1.async_close()
    await conn2.async_close()
    await srv.async_close()
