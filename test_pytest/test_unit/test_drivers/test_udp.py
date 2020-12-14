import pytest
import asyncio

from hat.drivers import udp


@pytest.mark.asyncio
async def test_create(unused_udp_port):

    addr = ('127.0.0.1', unused_udp_port)

    ep1 = await udp.create(local_addr=addr)
    ep2 = await udp.create(remote_addr=addr)

    assert not ep1.is_closed
    assert not ep2.is_closed

    await asyncio.gather(ep1.async_close(), ep2.async_close())

    assert ep1.is_closed
    assert ep2.is_closed


@pytest.mark.asyncio
async def test_send_receive(unused_udp_port):

    addr = ('127.0.0.1', unused_udp_port)

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

    await asyncio.gather(ep1.async_close(), ep2.async_close())
