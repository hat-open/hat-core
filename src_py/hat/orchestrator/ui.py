"""UI web server"""

from pathlib import Path
import contextlib
import logging
import typing
import urllib

from hat import aio
from hat import json
from hat import juggler
from hat import util
import hat.orchestrator.component


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

autoflush_delay: float = 0.2
"""Jugler autoflush delay"""


async def create(conf: json.Data,
                 path: Path,
                 components: typing.List[hat.orchestrator.component.Component]
                 ) -> 'WebServer':
    """Create ui for monitoring and controlling components

    Args:
        conf: configuration defined by
            ``hat://orchestrator.yaml#/definitions/ui``
        path: web ui directory path
        components: components

    """
    srv = WebServer()
    srv._async_group = aio.Group()
    srv._components = components
    srv._change_registry = util.CallbackRegistry()

    for component in components:
        srv._async_group.spawn(srv._component_loop, component)

    addr = urllib.parse.urlparse(conf['address'])
    juggler_srv = await juggler.listen(
        addr.hostname, addr.port,
        lambda conn: srv._async_group.spawn(srv._conn_loop, conn),
        static_dir=path,
        autoflush_delay=autoflush_delay)
    srv._async_group.spawn(aio.call_on_cancel, juggler_srv.async_close)

    return srv


class WebServer(aio.Resource):
    """WebServer

    For creating new instance of this class see :func:`create`

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    def _set_data(self, conn):
        data = {
            'components': [{
                'id': idx,
                'name': component.name,
                'delay': component.delay,
                'revive': component.revive,
                'status': component.status.name
            } for idx, component in enumerate(self._components)]}
        with contextlib.suppress(ConnectionError):
            conn.set_local_data(data)

    async def _component_loop(self, component):
        with component.register_change_cb(self._change_registry.notify):
            await component.wait_closed()

    async def _conn_loop(self, conn):
        try:
            self._set_data(conn)

            with self._change_registry.register(lambda: self._set_data(conn)):
                while True:
                    msg = await conn.receive()
                    fn = {'start': self._process_msg_start,
                          'stop': self._process_msg_stop,
                          'revive': self._process_msg_revive}.get(msg['type'])
                    if not fn:
                        raise Exception('received invalid message type')
                    fn(msg['payload'])
        except ConnectionError:
            pass
        finally:
            await conn.async_close()

    def _process_msg_start(self, payload):
        component = self._components[payload['id']]
        component.start()

    def _process_msg_stop(self, payload):
        component = self._components[payload['id']]
        component.stop()

    def _process_msg_revive(self, payload):
        component = self._components[payload['id']]
        component.set_revive(bool(payload['value']))
