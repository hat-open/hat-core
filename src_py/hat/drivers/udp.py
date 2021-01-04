"""Asyncio UDP endpoint wrapper"""

import asyncio
import typing

from hat import aio


class Address(typing.NamedTuple):
    host: str
    port: int


async def create(local_addr: typing.Optional[Address] = None,
                 remote_addr: typing.Optional[Address] = None,
                 queue_size: int = 0,
                 **kwargs
                 ) -> 'Endpoint':
    """Create new UDP endpoint

    Args:
        local_addr: local address
        remote_addr: remote address
        queue_size: receive queue max size
        kwargs: additional arguments passed to
            :meth:`asyncio.AbstractEventLoop.create_datagram_endpoint`

    """
    endpoint = Endpoint()
    endpoint._local_addr = local_addr
    endpoint._remote_addr = remote_addr
    endpoint._async_group = aio.Group()
    endpoint._queue = aio.Queue(queue_size)

    class Protocol(asyncio.DatagramProtocol):

        def connection_lost(self, exc):
            endpoint._async_group.close()

        def datagram_received(self, data, addr):
            endpoint._queue.put_nowait((data, Address(addr[0], addr[1])))

    loop = asyncio.get_running_loop()
    endpoint._transport, endpoint._protocol = \
        await loop.create_datagram_endpoint(Protocol, local_addr, remote_addr,
                                            **kwargs)
    endpoint._async_group.spawn(aio.call_on_cancel, endpoint._transport.close)
    endpoint._async_group.spawn(aio.call_on_cancel, endpoint._queue.close)
    return endpoint


class Endpoint(aio.Resource):
    """UDP endpoint"""

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def empty(self) -> bool:
        """Is receive queue empty"""
        return self._queue.empty()

    def send(self,
             data: bytes,
             remote_addr: typing.Optional[Address] = None):
        """Send datagram

        If `remote_addr` is not set, `remote_addr` passed to :func:`create`
        is used.

        """
        self._transport.sendto(data, remote_addr or self._remote_addr)

    async def receive(self) -> typing.Tuple[bytes, Address]:
        """Receive datagram"""
        data, addr = await self._queue.get()
        return data, addr
