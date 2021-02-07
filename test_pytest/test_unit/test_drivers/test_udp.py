import asyncio

import pytest

from hat import util
from hat.drivers import udp


pytestmark = pytest.mark.asyncio


@pytest.fixture
def addr():
    return udp.Address('127.0.0.1', util.get_unused_udp_port())


async def test_create(addr):
    ep1 = await udp.create(local_addr=addr)
    ep2 = await udp.create(remote_addr=addr)

    assert not ep1.is_closed
    assert not ep2.is_closed

    await asyncio.gather(ep1.async_close(), ep2.async_close())

    assert ep1.is_closed
    assert ep2.is_closed


async def test_send_receive(addr):
    ep1 = await udp.create(local_addr=addr)
    ep2 = await udp.create(remote_addr=addr)

    assert ep1.empty
    assert ep2.empty

    send_data = b'123'
    ep2.send(send_data)
    receive_data, ep2_addr = await ep1.receive()
    assert send_data == receive_data
    assert addr != ep2_addr

    assert ep1.empty
    assert ep2.empty

    send_data = b'abc'
    ep1.send(send_data, ep2_addr)
    receive_data, ep1_addr = await ep2.receive()
    assert send_data == receive_data
    assert addr == ep1_addr

    assert ep1.empty
    assert ep2.empty

    await ep1.async_close()
    await ep2.async_close()
