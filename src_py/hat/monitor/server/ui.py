"""Implementation of web server UI"""

from pathlib import Path
import logging
import urllib

from hat import aio
from hat import json
from hat import juggler
import hat.monitor.server.server


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

autoflush_delay: float = 0.2
"""Juggler autoflush delay"""


async def create(conf: json.Data,
                 path: Path,
                 server: hat.monitor.server.server.Server
                 ) -> 'WebServer':
    """Create user interface

    Args:
        conf: configuration defined by
            ``hat://monitor/main.yaml#/definitions/ui``
        path: web ui directory path
        server: local monitor server

    """
    addr = urllib.parse.urlparse(conf['address'])

    srv = WebServer()
    srv._server = server

    srv._srv = await juggler.listen(host=addr.hostname,
                                    port=addr.port,
                                    connection_cb=srv._on_connection,
                                    static_dir=path,
                                    autoflush_delay=autoflush_delay)

    mlog.debug("web server listening on %s", conf['address'])
    return srv


class WebServer(aio.Resource):
    """Web server UI

    For creating new instance of this class see :func:`create`

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._srv.async_group

    def _on_connection(self, conn):
        connection = _Connection(conn, self._server)
        self.async_group.spawn(connection.connection_loop)


class _Connection:

    def __init__(self, conn, server):
        self._conn = conn
        self._server = server

    async def connection_loop(self):
        try:
            mlog.debug('connection established')

            with self._server.register_change_cb(self._on_server_change):
                self._on_server_change()

                while True:
                    msg = await self._conn.receive()

                    if msg['type'] == 'set_rank':
                        self._process_set_rank(msg['payload'])

                    else:
                        raise Exception('unsupported message type')

        except ConnectionError:
            pass

        except Exception as e:
            mlog.warning('connection loop error: %s', e, exc_info=e)

        finally:
            self._conn.close()
            mlog.debug('connection closed')

    def _on_server_change(self):
        local_components = [{'cid': i.cid,
                             'name': i.name,
                             'group': i.group,
                             'address': i.address,
                             'rank': i.rank}
                            for i in self._server.local_components]
        global_components = [{'cid': i.cid,
                              'mid': i.mid,
                              'name': i.name,
                              'group': i.group,
                              'address': i.address,
                              'rank': i.rank,
                              'blessing': i.blessing,
                              'ready': i.ready}
                             for i in self._server.global_components]
        data = {'mid': self._server.mid,
                'local_components': local_components,
                'global_components': global_components}
        self._conn.set_local_data(data)

    def _process_set_rank(self, payload):
        self._server.set_rank(payload['cid'], payload['rank'])
