"""Syslog server implementation

Attributes:
    mlog (logging.Logger): module logger

"""

import asyncio.sslproto
import contextlib
import datetime
import functools
import logging
import ssl
import urllib.parse

from hat import aio
from hat.syslog.server import common


mlog = logging.getLogger(__name__)


async def create_syslog_server(conf, backend):
    """Create syslog server

    Args:
        conf (hat.syslog.server.conf.SysLogServer): configuration
        backend (hat.syslog.server.backend.Backend): backend

    Returns:
        SysLogServer

    """
    addr = urllib.parse.urlparse(conf.addr)
    if addr.scheme == 'ssl':
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        ssl_ctx.load_cert_chain(conf.pem)
    else:
        ssl_ctx = None

    async_group = aio.Group()
    srv = await asyncio.start_server(
        functools.partial(async_group.spawn, _client_loop, backend),
        addr.hostname, addr.port, ssl=ssl_ctx)
    async_group.spawn(aio.call_on_cancel, _asyncio_async_close, srv)

    mlog.debug('listening for syslog clients on %s:%s',
               addr.hostname, addr.port)

    srv = SysLogServer()
    srv._async_group = async_group
    return srv


class SysLogServer:
    """Syslog server

    For creating new instance see :func:`create_syslog_server`.

    """

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()


async def _client_loop(backend, reader, writer):
    try:
        while True:
            size = await reader.readuntil(b' ')
            buff = await reader.readexactly(int(size[:-1]))
            t = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
            msg = common.msg_from_str(buff.decode())
            mlog.debug("received new syslog message")
            await backend.register(t, msg)
    except asyncio.IncompleteReadError:
        pass
    except Exception as e:
        mlog.warning('syslog client error: %s', e, exc_info=e)
    finally:
        # BUGFIX
        if isinstance(writer.transport,
                      asyncio.sslproto._SSLProtocolTransport):
            # TODO for SSL connection Protocol.connection_lost is never called
            writer.close()
            await aio.uncancellable(asyncio.sleep(0.001))
        else:
            await aio.uncancellable(_asyncio_async_close(writer))
        mlog.debug('syslog client connection closed')


async def _asyncio_async_close(x):
    with contextlib.suppress(Exception):
        x.close()
    await x.wait_closed()
