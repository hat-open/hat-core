"""Asyncio TCP wrapper"""

import asyncio
import logging
import typing

from hat import aio


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


class Address(typing.NamedTuple):
    host: str
    port: int


class ConnectionInfo(typing.NamedTuple):
    local_addr: Address
    remote_addr: Address


ConnectionCb = aio.AsyncCallable[['Connection'], None]
"""Connection callback"""


async def connect(addr: Address,
                  **kwargs
                  ) -> 'Connection':
    """Create TCP connection

    Additional arguments are passed directly to `asyncio.open_connection`.

    """
    reader, writer = await asyncio.open_connection(addr.host, addr.port,
                                                   **kwargs)
    return Connection(reader, writer)


async def listen(connection_cb: ConnectionCb,
                 addr: Address,
                 *,
                 bind_connections: bool = False,
                 **kwargs
                 ) -> 'Server':
    """Create listening server

    If `bind_connections` is ``True``, closing server will close all open
    incoming connections.

    Additional arguments are passed directly to `asyncio.start_server`.

    """
    server = Server()
    server._connection_cb = connection_cb
    server._bind_connections = bind_connections
    server._async_group = aio.Group()

    server._srv = await asyncio.start_server(server._on_connection,
                                             addr.host, addr.port, **kwargs)
    server._async_group.spawn(aio.call_on_cancel, server._on_close)

    socknames = (socket.getsockname() for socket in server._srv.sockets)
    server._addresses = [Address(*sockname[:2]) for sockname in socknames]

    return server


class Server(aio.Resource):
    """TCP listening server

    Closing server will cancel all running `connection_cb` coroutines.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def addresses(self) -> typing.List[Address]:
        """Listening addresses"""
        return self._addresses

    async def _on_close(self):
        self._srv.close()
        await self._srv.wait_closed()

    def _on_connection(self, reader, writer):
        try:
            conn_async_group = (self._async_group.create_subgroup()
                                if self._bind_connections else None)
            conn = Connection(reader, writer, conn_async_group)

        except Exception:
            reader.close()
            return

        try:
            self._async_group.spawn(self._async_connection_cb, conn)

        except Exception:
            conn.close()

    async def _async_connection_cb(self, conn):
        try:
            await aio.call(self._connection_cb, conn)

        except Exception as e:
            mlog.warning('connection callback error: %s', e, exc_info=e)
            await aio.uncancellable(conn.async_close())

        except asyncio.CancelledError:
            await aio.uncancellable(conn.async_close())
            raise


class Connection(aio.Resource):
    """TCP connection"""

    def __init__(self,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 async_group: typing.Optional[aio.Group] = None):
        self._reader = reader
        self._writer = writer
        self._read_queue = aio.Queue()
        self._async_group = async_group or aio.Group()
        self._async_group.spawn(self._read_loop)

        sockname = writer.get_extra_info('sockname')
        peername = writer.get_extra_info('peername')
        self._info = ConnectionInfo(
            local_addr=Address(sockname[0], sockname[1]),
            remote_addr=Address(peername[0], peername[1]))

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def info(self) -> ConnectionInfo:
        """Connection info"""
        return self._info

    def write(self, data: bytes):
        """Write data

        See `asyncio.StreamWriter.write`.

        """
        self._writer.write(data)

    async def drain(self):
        """Drain stream writer

        See `asyncio.StreamWriter.drain`.

        """
        await self._writer.drain()

    async def read(self,
                   n: int = -1
                   ) -> bytes:
        """Read up to `n` bytes

        If EOF is detected and no new bytes are available, `ConnectionError`
        is raised.

        See `asyncio.StreamReader.read`.

        """
        if n == 0:
            return b''

        future = asyncio.Future()
        try:
            self._read_queue.put_nowait((future, False, n))
            return await future

        except aio.QueueClosedError:
            raise ConnectionError()

    async def readexactly(self,
                          n: int
                          ) -> bytes:
        """Read exactly `n` bytes

        If exact number of bytes could not be read, `ConnectionError` is
        raised.

        See `asyncio.StreamReader.readexactly`.

        """
        if n < 1:
            return b''

        future = asyncio.Future()
        try:
            self._read_queue.put_nowait((future, True, n))
            return await future

        except aio.QueueClosedError:
            raise ConnectionError()

    async def _read_loop(self):
        future = None
        try:
            while True:
                future, is_exact, n = await self._read_queue.get()

                if is_exact:
                    data = await self._reader.readexactly(n)
                else:
                    data = await self._reader.read(n)

                if not data:
                    break
                future.set_result(data)

        except asyncio.IncompleteReadError:
            pass

        except Exception as e:
            mlog.warning("read loop error: %s", e, exc_info=e)

        finally:
            self._async_group.close()
            self._read_queue.close()

            while True:
                if future and not future.done():
                    future.set_exception(ConnectionError())
                if self._read_queue.empty():
                    break
                future, _, _ = self._read_queue.get_nowait()

            self._writer.close()
            await aio.uncancellable(self._writer.wait_closed())
