import contextlib
import logging
import urllib

from hat import juggler
from hat import util
from hat.util import aio

mlog = logging.getLogger(__name__)


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
    srv._cb_handles = [
        component.register_change_cb(srv._change_registry.notify)
        for component in components]
    addr = urllib.parse.urlparse(conf['address'])
    juggler_srv = await juggler.listen(
        f'ws://{addr.hostname}:{addr.port}/ws',
        lambda conn: srv._async_group.spawn(srv._conn_loop, conn),
        static_path=path)
    srv._async_group.spawn(aio.call_on_cancel, juggler_srv.async_close)
    return srv


class WebServer:
    """WebServer

    For creating new instance of this class see :func:`create`

    """

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Close web server and all active connections"""
        for handle in self._cb_handles:
            handle.cancel()
        await self._async_group.async_close()

    def _set_data(self, conn):
        data = {
            'components': [{
                'id': idx,
                'name': component.name,
                'delay': component.delay,
                'revive': component.revive,
                'status': component.status.name
            } for idx, component in enumerate(self._components)]}
        with contextlib.suppress(juggler.ConnectionClosedError):
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
        except juggler.ConnectionClosedError:
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
