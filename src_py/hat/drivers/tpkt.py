"""Transport protocol on top of TCP

Attributes:
    mlog (logging.Logger): module logger

"""

import asyncio
import contextlib
import itertools
import logging

from hat import util
from hat.util import aio


mlog = logging.getLogger(__name__)


Address = util.namedtuple(
    'Address',
    ['host', 'str: host name'],
    ['port', 'int: TCP port', 102])


ConnectionInfo = util.namedtuple(
    'ConnectionInfo',
    ['local_addr', "Address: local address"],
    ['remote_addr', "Address: remote address"])


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
        connection_cb (Callable[[Connection],None]): new connection callback
        addr (Address): local listening address

    Returns:
        Server

    """

    def on_connection(reader, writer):
        try:
            try:
                conn = _create_connection(reader, writer, group)
            except Exception as e:
                group.spawn(_asyncio_async_close, writer)
                raise e
            try:
                connection_cb(conn)
            except Exception as e:
                group.spawn(conn.async_close)
                raise e
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
        """List[Tuple[str,int]]: listening (IP address, TCP port) pairs"""
        return self._addresses

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._group.closed

    async def async_close(self):
        """Close listening socket

        Calling this method closes all active established connections

        """
        await self._group.async_close()


def _create_connection(reader, writer, parent_group=None):
    sockname = writer.get_extra_info('sockname')
    peername = writer.get_extra_info('peername')
    info = ConnectionInfo(local_addr=Address(sockname[0], sockname[1]),
                          remote_addr=Address(peername[0], peername[1]))

    conn = Connection()
    conn._reader = reader
    conn._writer = writer
    conn._info = info
    conn._group = (parent_group.create_subgroup() if parent_group
                   else aio.Group())
    conn._group.spawn(aio.call_on_cancel, _asyncio_async_close,
                      writer, flush=True)

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
            bytes

        """
        header = await self._reader.readexactly(4)
        if header[0] != 3:
            raise Exception(f"invalid vrsn number - expected 3 but "
                            f"received {header[0]}")
        packet_length = (header[2] << 8) | header[3]
        if packet_length < 7:
            raise Exception(f"invalid packet length - expected greater than 7 "
                            f"but received {packet_length}")
        data_length = packet_length - 4
        data = await self._reader.readexactly(data_length)
        return data

    def write(self, data):
        """Write data

        Args:
            data (bytes): data

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


async def _asyncio_async_close(x, flush=False):
    if flush:
        with contextlib.suppress(Exception):
            await x.flush()
    with contextlib.suppress(Exception):
        x.close()
    await x.wait_closed()
