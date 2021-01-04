"""Transport protocol on top of TCP

Attributes:
    mlog (logging.Logger): module logger

"""

import asyncio
import contextlib
import itertools
import logging
import typing

from hat import aio


mlog = logging.getLogger(__name__)


Data = typing.Union[bytes, bytearray, memoryview]
"""Data"""


class Address(typing.NamedTuple):
    host: str
    port: int = 102


class ConnectionInfo(typing.NamedTuple):
    local_addr: Address
    remote_addr: Address


ConnectionCb = aio.AsyncCallable[['Connection'], None]
"""Connection callback"""


async def connect(addr: Address) -> 'Connection':
    """Create new TPKT connection"""
    reader, writer = await asyncio.open_connection(addr.host, addr.port)
    try:
        return _create_connection(reader, writer)
    except Exception:
        await aio.uncancellable(_asyncio_async_close(writer))
        raise


async def listen(connection_cb: ConnectionCb,
                 addr: Address = Address('0.0.0.0', 102)
                 ) -> 'Server':
    """Create new TPKT listening server

    Args:
        connection_cb: new connection callback
        addr: local listening address

    """
    def on_connection(reader, writer):
        async_group.spawn(on_connection_async, reader, writer)

    async def on_connection_async(reader, writer):
        try:
            try:
                conn = _create_connection(reader, writer)
            except Exception:
                await aio.uncancellable(_asyncio_async_close(writer))
                raise
            try:
                await aio.call(connection_cb, conn)
            except BaseException:
                await aio.uncancellable(conn.async_close())
                raise
        except Exception as e:
            mlog.error("error creating new incomming connection: %s", e,
                       exc_info=e)

    async_group = aio.Group()
    tcp_server = await asyncio.start_server(on_connection, addr.host,
                                            addr.port)
    async_group.spawn(aio.call_on_cancel, _asyncio_async_close, tcp_server)

    socknames = [socket.getsockname() for socket in tcp_server.sockets]
    addresses = [Address(*sockname[:2]) for sockname in socknames]

    srv = Server()
    srv._addresses = addresses
    srv._async_group = async_group
    return srv


class Server(aio.Resource):
    """TPKT listening server

    For creation of new instance see :func:`listen`.

    Closing server doesn't close active incomming connections.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def addresses(self) -> typing.List[Address]:
        """Listening addresses"""
        return self._addresses


def _create_connection(reader, writer):
    sockname = writer.get_extra_info('sockname')
    peername = writer.get_extra_info('peername')
    info = ConnectionInfo(local_addr=Address(sockname[0], sockname[1]),
                          remote_addr=Address(peername[0], peername[1]))

    conn = Connection()
    conn._reader = reader
    conn._writer = writer
    conn._info = info
    conn._read_queue = aio.Queue()
    conn._async_group = aio.Group()
    conn._async_group.spawn(conn._read_loop)
    return conn


class Connection(aio.Resource):
    """TPKT connection

    For creation of new instance see :func:`connect`

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def info(self) -> ConnectionInfo:
        """Connection info"""
        return self._info

    async def read(self) -> Data:
        """Read data"""
        return await self._read_queue.get()

    def write(self, data: Data):
        """Write data"""
        data_len = len(data)
        if data_len > 0xFFFB:
            raise Exception("data length greater than 0xFFFB")
        if data_len < 3:
            raise Exception("data length less than 3")
        packet_length = data_len + 4
        self._writer.write(bytes(itertools.chain(
            [3, 0, packet_length >> 8, packet_length & 0xFF],
            data)))

    async def _read_loop(self):
        try:
            while True:
                header = await self._reader.readexactly(4)
                if header[0] != 3:
                    raise Exception(f"invalid vrsn number "
                                    f"(received {header[0]})")
                packet_length = (header[2] << 8) | header[3]
                if packet_length < 7:
                    raise Exception(f"invalid packet length "
                                    f"(received {packet_length})")
                data_length = packet_length - 4
                data = await self._reader.readexactly(data_length)
                await self._read_queue.put(data)
        except Exception as e:
            mlog.error("error while reading: %s", e, exc_info=e)
        finally:
            self._async_group.close()
            self._read_queue.close()
            await aio.uncancellable(_asyncio_async_close(self._writer, True))


async def _asyncio_async_close(x, flush=False):
    if flush:
        with contextlib.suppress(Exception):
            await x.flush()
    with contextlib.suppress(Exception):
        x.close()
    with contextlib.suppress(ConnectionError):
        await x.wait_closed()
