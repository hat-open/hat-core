"""Asyncio UDP endpoint wrapper"""

import asyncio

from hat import aio
from hat import util


Address = util.namedtuple(
    'Address',
    ['host', 'str'],
    ['port', 'int'])


async def create(local_addr=None, remote_addr=None, queue_size=0, **kwargs):
    """Create new UDP endpoint

    Args:
        local_addr (Optional[Address]): local address
        remote_addr (Optional[Address]): remote address
        queue_size (int): receive queue max size
        kwargs: additional arguments passed to
            :meth:`asyncio.AbstractEventLoop.create_datagram_endpoint`

    Returns:
        Endpoint

    """
    endpoint = Endpoint()
    endpoint._local_addr = local_addr
    endpoint._remote_addr = remote_addr
    endpoint._closed = asyncio.Future()
    endpoint._queue = aio.Queue(queue_size)

    class Protocol(asyncio.DatagramProtocol):

        def connection_lost(self, exc):
            endpoint._queue.close()
            endpoint._closed.set_result(True)

        def datagram_received(self, data, addr):
            endpoint._queue.put_nowait((data, Address(addr[0], addr[1])))

    loop = asyncio.get_running_loop()
    endpoint._transport, endpoint._protocol = \
        await loop.create_datagram_endpoint(Protocol, local_addr, remote_addr,
                                            **kwargs)
    return endpoint


class Endpoint:
    """UDP endpoint"""

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return asyncio.shield(self._closed)

    @property
    def empty(self):
        """bool: is receive queue empty"""
        return self._queue.empty()

    async def async_close(self):
        """Async close"""
        self._close()
        await self.closed

    def send(self, data, remote_addr=None):
        """Send datagram

        If `remote_addr` is not set, `remote_addr` passed to :func:`create`
        is used.

        Args:
            data (bytes): data
            remote_addr (Optional[Address]): address

        """
        self._transport.sendto(data, remote_addr or self._remote_addr)

    async def receive(self):
        """Receive datagram

        Returns:
            Tuple[bytes,Address]

        """
        data, addr = await self._queue.get()
        return data, addr

    def _close(self):
        self._transport.close()
