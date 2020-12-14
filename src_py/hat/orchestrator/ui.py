import contextlib
import logging
import urllib

from hat import aio
from hat import juggler
from hat import util

mlog = logging.getLogger(__name__)


autoflush_delay = 0.2


async def create(conf, path, components):
    """Create ui for monitoring and controlling components

    Args:
        conf (hat.json.Data): configuration defined by
            ``hat://orchestrator.yaml#/definitions/ui``
        path (pathlib.Path): web ui directory path
        components (List[hat.orchestrator.component.Component]): components

    Returns:
        WebServer

    """
    srv = WebServer()
    srv._async_group = aio.Group()
    srv._components = components
    srv._change_registry = util.CallbackRegistry()

    cb_handles = [component.register_change_cb(srv._change_registry.notify)
                  for component in components]

    def close_cb_handles():
        for cb_handle in cb_handles:
            cb_handle.cancel()

    srv._async_group.spawn(aio.call_on_cancel, close_cb_handles)

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
