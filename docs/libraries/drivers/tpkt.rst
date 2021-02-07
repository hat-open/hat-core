.. _hat-drivers-tpkt:

`hat.drivers.tpkt` - Transport Service on top of TCP
=====================================================

Implementation of `TPKT <https://tools.ietf.org/html/rfc983>`_ based on
asyncio.

::

    Data = typing.Union[bytes, bytearray, memoryview]

    class Address(typing.NamedTuple):
        host: str
        port: int = 102

    class ConnectionInfo(typing.NamedTuple):
        local_addr: Address
        remote_addr: Address

    ConnectionCb = aio.AsyncCallable[['Connection'], None]

    async def connect(addr: Address) -> 'Connection': ...

    async def listen(connection_cb: ConnectionCb,
                     addr: Address = Address('0.0.0.0', 102)
                     ) -> 'Server': ...

    class Server(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

        @property
        def addresses(self) -> typing.List[Address]: ...

    class Connection(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

        @property
        def info(self) -> ConnectionInfo: ...

        async def read(self) -> Data: ...

        def write(self, data: Data): ...

Example usage::

    conn1_future = asyncio.Future()
    srv = await tpkt.listen(conn1_future.set_result, addr)
    conn2 = await tpkt.connect(addr)
    conn1 = await conn1_future

    write_data = b'12345'
    conn1.write(write_data)
    read_data = await conn2.read()
    assert write_data == read_data

    await conn1.async_close()
    await conn2.async_close()
    await srv.async_close()


API
---

API reference is available as part of generated documentation:

    * `Python hat.drivers.tpkt module <../../pyhat/hat/drivers/tpkt.html>`_
