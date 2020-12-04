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
from hat import util


mlog = logging.getLogger(__name__)


Data = typing.Union[bytes, bytearray, memoryview]
"""Data"""


Address = util.namedtuple(
    'Address',
    ['host', 'str: host name'],
    ['port', 'int: TCP port', 102])


ConnectionInfo = util.namedtuple(
    'ConnectionInfo',
    ['local_addr', "Address: local address"],
    ['remote_addr', "Address: remote address"])


ConnectionCb = aio.AsyncCallable[['Connection'], None]
"""Connection callback"""


async def connect(addr):
    """Create new TPKT connection

    Args:
        addr (Address): remote address

    Returns:
        Connection

    """
    reader, writer = await asyncio.open_connection(addr.host, addr.port)
    try:
        return _create_connection(reader, writer)
    except Exception:
        await aio.uncancellable(_asyncio_async_close(writer))
        raise


async def listen(connection_cb, addr=Address('0.0.0.0', 102)):
    """Create new TPKT listening server

    Args:
        connection_cb (ConnectionCb): new connection callback
        addr (Address): local listening address

    Returns:
        Server

    """
    def on_connection(reader, writer):
        group.spawn(on_connection_async, reader, writer)

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

    group = aio.Group()
    tcp_server = await asyncio.start_server(on_connection, addr.host,
                                            addr.port)
    group.spawn(aio.call_on_cancel, _asyncio_async_close, tcp_server)

    socknames = [socket.getsockname() for socket in tcp_server.sockets]
    addresses = [Address(*sockname[:2]) for sockname in socknames]

    srv = Server()
    srv._addresses = addresses
    srv._group = group
    return srv


class Server:
    """TPKT listening server

    For creation of new instance see :func:`listen`

    """

    @property
    def addresses(self):
        """List[Address]: listening addresses"""
        return self._addresses

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._group.closed

    async def async_close(self):
        """Close listening socket

        Calling this method doesn't close active incomming connections

        """
        await self._group.async_close()


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
    conn._group = aio.Group()
    conn._group.spawn(conn._read_loop)
    return conn


class Connection:
    """TPKT connection

    For creation of new instance see :func:`connect`

    """

    @property
    def info(self):
        """ConnectionInfo: connection info"""
        return self._info

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._group.closed

    async def async_close(self):
        """Async close"""
        await self._group.async_close()

    async def read(self):
        """Read data

        Returns:
            Data

        """
        return await self._read_queue.get()

    def write(self, data):
        """Write data

        Args:
            data (Data): data

        """
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
            self._group.close()
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
