import hashlib
import logging
import secrets
import urllib

from hat import aio
from hat import json
from hat import juggler
from hat import util
from hat.gui import common


mlog = logging.getLogger(__name__)


async def create(conf, path, adapters, views):
    """Create server

    Args:
        conf (json.Data): configuration defined by
            ``hat://gui/main.yaml#/definitions/server``
        path (pathlib.Path): web ui directory path
        adapters (Dict[str,common.Adapter]): adapters
        views (hat.gui.view.ViewManager): view manager

    Return:
        Server

    """
    srv = Server()
    srv._async_group = aio.Group()
    srv._conf = conf
    srv._adapters = adapters
    srv._views = views
    srv._users = {i['name']: i for i in conf['users']}
    srv._roles = {i['name']: i for i in conf['roles']}

    addr = urllib.parse.urlparse(conf['address'])
    juggler_srv = await juggler.listen(
        addr.hostname, addr.port,
        lambda conn: srv._async_group.spawn(srv._conn_loop, conn),
        static_dir=path)
    srv._async_group.spawn(aio.call_on_cancel, juggler_srv.async_close)
    return srv


class Server(aio.Resource):
    """Server"""

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def _conn_loop(self, conn):
        initial_view = self._conf['initial_view']
        session = None
        try:
            await self._show_view(conn, initial_view, reason='init')
            while True:
                msg = await conn.receive()
                if msg['type'] == 'login':
                    if session:
                        await session.async_close()
                    session = await self._login(
                        conn, msg['name'], msg['password'])
                elif msg['type'] == 'logout':
                    if session:
                        await session.async_close()
                        session = None
                    await self._show_view(conn, initial_view, reason='logout')
                elif msg['type'] == 'adapter':
                    if not session:
                        continue
                    session.add_adapter_message(msg['name'], msg['data'])
                else:
                    raise Exception('received invalid message type')
        except ConnectionError:
            pass
        finally:
            if session:
                await session.async_close()
            await conn.async_close()

    async def _login(self, conn, name, password):
        initial_view = self._conf['initial_view']
        user = self._authenticate(name, password)
        if not user:
            await self._show_view(conn, initial_view, reason='auth_fail')
            return
        roles = [self._roles[i] for i in user['roles']]
        if not roles:
            mlog.warning('user %s has no roles', user['name'])
            await self._show_view(conn, initial_view, reason='internal_error')
            return
        await self._show_view(conn, roles[0]['view'], reason='login',
                              username=user['name'], roles=user['roles'])
        adapters = {i: self._adapters[i]
                    for role in roles
                    for i in role['adapters']}
        return await create_session(conn, user['name'], user['roles'],
                                    adapters)

    def _authenticate(self, name, password):
        user = self._users.get(name)
        if not user:
            return
        m = hashlib.sha256(bytes.fromhex(user['password']['salt']))
        m.update(password.encode())
        hash = m.hexdigest()
        # cryptographically secure comparison to prevent timing attacks
        if not secrets.compare_digest(user['password']['hash'], hash):
            return
        return user

    async def _show_view(self, conn, name,  reason='init',
                         username=None, roles=[]):
        view = await self._views.get(name)
        conn.set_local_data(None)
        await conn.flush_local_data()
        await conn.send({'type': 'state',
                         'user': username,
                         'roles': roles,
                         'reason': reason,
                         'view': view.data,
                         'conf': view.conf})
        conn.set_local_data({})
        await conn.flush_local_data()


async def create_session(conn, user, roles, adapters):
    """Create client session

    `adapters` contain only adapters associated with `roles`.

    Args:
        conn (juggler.Connection): juggler connection
        user (str): user identifier
        roles (List[str]): user roles
        adapters (Dict[str,common.Adapter]): adapters

    Return:
        Session

    """
    session = Session()
    session._async_group = aio.Group()
    session._queues = {}
    for name, adapter in adapters.items():
        queue = aio.Queue()
        client = _AdapterSessionClientImpl(name, conn, queue, user, roles)
        session._async_group.spawn(aio.call_on_cancel, client.close)
        adapter_session = await adapter.create_session(client)
        session._async_group.spawn(aio.call_on_cancel,
                                   adapter_session.async_close)
        session._queues[name] = queue
    return session


class Session(aio.Resource):
    """Client session"""

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    def add_adapter_message(self, name, msg):
        """Add adapter message

        Args:
            name (str): adapter name
            msg (json.Data): message

        """
        if name in self._queues:
            self._queues[name].put_nowait(msg)


class _AdapterSessionClientImpl(common.AdapterSessionClient):

    def __init__(self, name, conn, queue, user, roles):
        self._name = name
        self._conn = conn
        self._queue = queue
        self._user = user
        self._roles = roles
        self._cached_remote_data = self.remote_data
        self._change_cbs = util.CallbackRegistry()
        self._cb_handle = self._conn.register_change_cb(self._on_change)

    def close(self):
        """close adapter session client"""
        self._cb_handle.cancel()

    @property
    def user(self):
        """See :meth:`common.AdapterSessionClient.user`"""
        return self._user

    @property
    def roles(self):
        """See :meth:`common.AdapterSessionClient.roles`"""
        return self._roles

    @property
    def local_data(self):
        """See :meth:`common.AdapterSessionClient.local_data`"""
        if not isinstance(self._conn.local_data, dict):
            return
        return self._conn.local_data.get(self._name)

    @property
    def remote_data(self):
        """See :meth:`common.AdapterSessionClient.remote_data`"""
        if not isinstance(self._conn.remote_data, dict):
            return
        return self._conn.remote_data.get(self._name)

    def register_change_cb(self, cb):
        """See :meth:`common.AdapterSessionClient.register_change_cb`"""
        return self._change_cbs.register(cb)

    def set_local_data(self, data):
        """See :meth:`common.AdapterSessionClient.set_local_data`"""
        local_data = dict(self._conn.local_data)
        local_data[self._name] = data
        self._conn.set_local_data(local_data)

    async def send(self, msg):
        """See :meth:`common.AdapterSessionClient.send`"""
        await self._conn.send({'type': 'adapter',
                               'name': self._name,
                               'data': msg})

    async def receive(self):
        """See :meth:`common.AdapterSessionClient.receive`"""
        return await self._queue.get()

    def _on_change(self):
        if json.equals(self.remote_data, self._cached_remote_data):
            return
        self._cached_remote_data = self.remote_data
        self._change_cbs.notify()
