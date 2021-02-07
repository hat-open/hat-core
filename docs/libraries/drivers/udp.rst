.. _hat-drivers-udp:

`hat.drivers.udp` - User Datagram Protocol
==========================================

Asyncio wrapper for UDP communication.

::

    class Address(typing.NamedTuple):
        host: str
        port: int

    async def create(local_addr: typing.Optional[Address] = None,
                     remote_addr: typing.Optional[Address] = None,
                     queue_size: int = 0,
                     **kwargs
                     ) -> 'Endpoint': ...

    class Endpoint(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

        @property
        def empty(self) -> bool: ...

        def send(self,
                 data: bytes,
                 remote_addr: typing.Optional[Address] = None): ...

        async def receive(self) -> typing.Tuple[bytes, Address]: ...

Example usage::

    addr = udp.Address('127.0.0.1', util.get_unused_udp_port())

    # create two endpoints
    ep1 = await udp.create(local_addr=addr)
    ep2 = await udp.create(remote_addr=addr)

    # send from ep2 to ep1
    send_data = b'123'
    ep2.send(send_data)
    receive_data, ep2_addr = await ep1.receive()
    assert send_data == receive_data
    assert addr != ep2_addr

    # send from ep1 to ep2
    send_data = b'abc'
    ep1.send(send_data, ep2_addr)
    receive_data, ep1_addr = await ep2.receive()
    assert send_data == receive_data
    assert addr == ep1_addr

    # close endpoints
    await ep1.async_close()
    await ep2.async_close()


API
---

API reference is available as part of generated documentation:

    * `Python hat.drivers.udp module <../../pyhat/hat/drivers/udp.html>`_
