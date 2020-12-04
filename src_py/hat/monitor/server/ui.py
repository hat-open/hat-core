"""Implementation of web server UI

Attributes:
    mlog (logging.Logger): module logger
    autoflush_delay (float): juggler autoflush delay

"""

import contextlib
import logging
import urllib

from hat import aio
from hat import juggler


mlog = logging.getLogger(__name__)


autoflush_delay = 0.2


async def create(conf, path, server):
    """Create user interface

    Args:
        conf (hat.json.Data): configuration defined by
            ``hat://monitor/main.yaml#/definitions/ui``
        path (pathlib.Path): web ui directory path
        server (hat.monitor.server.Server): local monitor server

    Returns:
        WebServer

    """
    srv = WebServer()
    srv._monitor_server = server
    srv._async_group = aio.Group()
    addr = urllib.parse.urlparse(conf['address'])
    juggler_srv = await juggler.listen(
        addr.hostname, addr.port,
        lambda conn: srv._async_group.spawn(srv._connection_loop, conn),
        static_dir=path,
        autoflush_delay=autoflush_delay)
    srv._async_group.spawn(aio.call_on_cancel, juggler_srv.async_close)
    return srv


class WebServer:
    """Web server UI

    For creating new instance of this class see :func:`create`

    """

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Close web server and all active connections"""
        await self._async_group.async_close()

    async def _connection_loop(self, conn):
        try:
            self._set_data(conn)
            with self._monitor_server.register_change_cb(
                    lambda: self._set_data(conn)):
                while True:
                    msg = await conn.receive()
                    if msg['type'] != 'set_rank':
                        raise Exception('received invalid message type')
                    self._monitor_server.set_rank(cid=msg['payload']['cid'],
                                                  mid=msg['payload']['mid'],
                                                  rank=msg['payload']['rank'])
        except ConnectionError:
            pass
        finally:
            await conn.async_close()

    def _set_data(self, conn):
        data = {'mid': self._monitor_server.mid,
                'components': [{
                    'cid': component.cid,
                    'mid': component.mid,
                    'name': component.name,
                    'group': component.group,
                    'address': component.address,
                    'rank': component.rank,
                    'blessing': component.blessing,
                    'ready': component.ready
                } for component in self._monitor_server.components]}
        with contextlib.suppress(Exception):
            conn.set_local_data(data)
