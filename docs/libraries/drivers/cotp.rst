.. _hat-drivers-cotp:

`hat.drivers.cotp` - Connection oriented transport protocol
===========================================================

Asyncio implementation of COTP communication.

::

    Data = tpkt.Data

    Address = tpkt.Address

    class ConnectionInfo(typing.NamedTuple):
        local_addr: Address
        local_tsel: typing.Optional[int]
        remote_addr: Address
        remote_tsel: typing.Optional[int]

    ConnectionCb = aio.AsyncCallable[['Connection'], None]

    async def connect(addr: Address,
                      local_tsel: typing.Optional[int] = None,
                      remote_tsel: typing.Optional[int] = None
                      ) -> 'Connection': ...

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

        def write(self, data: bytes): ...

Example usage::

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


API
---

API reference is available as part of generated documentation:

    * `Python hat.drivers.cotp module <../../pyhat/hat/drivers/cotp.html>`_
