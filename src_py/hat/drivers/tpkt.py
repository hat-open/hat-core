"""Transport Service on top of TCP"""

import asyncio
import itertools
import logging
import typing

from hat import aio
from hat.drivers import tcp


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


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
    conn = await tcp.connect(tcp.Address(*addr))
    return Connection(conn)


async def listen(connection_cb: ConnectionCb,
                 addr: Address = Address('0.0.0.0')
                 ) -> 'Server':
    """Create new TPKT listening server"""
    server = Server()
    server._connection_cb = connection_cb
    server._srv = await tcp.listen(server._on_connection, tcp.Address(*addr))
    server._addresses = [Address(*i) for i in server._srv.addresses]
    return server


class Server(aio.Resource):
    """TPKT listening server

    For creation of new instance see `listen` coroutine.

    Closing server doesn't close active incoming connections.

    Closing server will cancel all running `connection_cb` coroutines.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._srv.async_group

    @property
    def addresses(self) -> typing.List[Address]:
        """Listening addresses"""
        return self._addresses

    async def _on_connection(self, conn):
        conn = Connection(conn)
        try:
            await aio.call(self._connection_cb, conn)

        except Exception as e:
            mlog.warning('connection callback error: %s', e, exc_info=e)
            await aio.uncancellable(conn.async_close())

        except asyncio.CancelledError:
            await aio.uncancellable(conn.async_close())
            raise


class Connection(aio.Resource):
    """TPKT connection"""

    def __init__(self, conn: tcp.Connection):
        self._conn = conn
        self._info = ConnectionInfo(*(Address(*i) for i in conn.info))
        self._read_queue = aio.Queue()
        conn.async_group.spawn(self._read_loop)

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._conn.async_group

    @property
    def info(self) -> ConnectionInfo:
        """Connection info"""
        return self._info

    async def read(self) -> bytes:
        """Read data"""
        try:
            return await self._read_queue.get()

        except aio.QueueClosedError:
            raise ConnectionError()

    def write(self, data: bytes):
        """Write data"""
        data_len = len(data)

        if data_len > 0xFFFB:
            raise ValueError("data length greater than 0xFFFB")

        if data_len < 3:
            raise ValueError("data length less than 3")

        packet_length = data_len + 4
        packet = bytes(itertools.chain(
            [3, 0, packet_length >> 8, packet_length & 0xFF],
            data))
        self._conn.write(packet)

    async def _read_loop(self):
        try:
            while True:
                header = await self._conn.readexactly(4)
                if header[0] != 3:
                    raise Exception(f"invalid vrsn number "
                                    f"(received {header[0]})")

                packet_length = (header[2] << 8) | header[3]
                if packet_length < 7:
                    raise Exception(f"invalid packet length "
                                    f"(received {packet_length})")

                data_length = packet_length - 4
                data = await self._conn.readexactly(data_length)
                await self._read_queue.put(data)

        except ConnectionError:
            pass

        except Exception as e:
            mlog.warning("read loop error: %s", e, exc_info=e)

        finally:
            self.close()
            self._read_queue.close()
