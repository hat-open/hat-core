.. _hat-drivers-tcp:

`hat.drivers.tcp` - Transmission Control Protocol
=================================================

Asyncio wrapper for TCP communication.

::

    class Address(typing.NamedTuple):
        host: str
        port: int

    class ConnectionInfo(typing.NamedTuple):
        local_addr: Address
        remote_addr: Address

    ConnectionCb = typing.Callable[['Connection'], None]

    async def connect(addr: Address,
                      **kwargs
                      ) -> 'Connection': ...


    async def listen(connection_cb: ConnectionCb,
                     addr: Address,
                     *,
                     bind_connections: bool = False,
                     **kwargs
                     ) -> 'Server': ...

    class Server(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

        @property
        def addresses(self) -> typing.List[Address]: ...

    class Connection(aio.Resource):

        def __init__(self,
                     reader: asyncio.StreamReader,
                     writer: asyncio.StreamWriter,
                     async_group: typing.Optional[aio.Group] = None): ...
        @property
        def async_group(self) -> aio.Group: ...

        @property
        def info(self) -> ConnectionInfo: ...

        def write(self, data: bytes): ...

        async def drain(self): ...

        async def read(self,
                       n: int = -1
                       ) -> bytes: ...

        async def readexactly(self,
                              n: int
                              ) -> bytes: ...

Example usage::

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


API
---

API reference is available as part of generated documentation:

    * `Python hat.drivers.tcp module <../../pyhat/hat/drivers/tcp.html>`_
