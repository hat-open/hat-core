"""GUI web server"""

from pathlib import Path
import functools
import hashlib
import logging
import typing
import urllib

from hat import aio
from hat import json
from hat import juggler
from hat import util
from hat.gui import common
import hat.gui.view


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

autoflush_delay: float = 0.2
"""Juggler autoflush delay"""


async def create_server(conf: json.Data,
                        ui_path: Path,
                        adapters: typing.Dict[str, common.Adapter],
                        views: hat.gui.view.ViewManager
                        ) -> 'Server':
    """Create server"""
    addr = urllib.parse.urlparse(conf['address'])
    initial_view = conf['initial_view']
    users = {i['name']: i for i in conf['users']}

    server = Server()

    connection_cb = functools.partial(_Connection, adapters, views,
                                      initial_view, users)
    server._srv = await juggler.listen(host=addr.hostname,
                                       port=addr.port,
                                       connection_cb=connection_cb,
                                       static_dir=ui_path,
                                       autoflush_delay=autoflush_delay)

    mlog.debug("web server listening on %s", conf['address'])
    return server


class Server(aio.Resource):
    """Server"""

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._srv.async_group


class _Connection(aio.Resource):

    def __init__(self, adapters, views, initial_view, users, conn):
        self._adapters = adapters
        self._views = views
        self._initial_view = initial_view
        self._users = users
        self._conn = conn
        self._session = None
        self.async_group.spawn(self._connection_loop)

    @property
    def async_group(self):
        return self._conn.async_group

    async def _connection_loop(self):
        try:
            await self._set_state(None, [], 'init', self._initial_view)

            while True:
                msg = await self._conn.receive()

                if msg['type'] == 'login':
                    await self._process_msg_login(msg)

                elif msg['type'] == 'logout':
                    await self._process_msg_logout(msg)

                elif msg['type'] == 'adapter':
                    await self._process_msg_adapter(msg)

                else:
                    raise Exception('received invalid message type')

        except (ConnectionError, aio.QueueClosedError):
            pass

        except Exception as e:
            mlog.warning('connection loop error: %s', e, exc_info=e)

        finally:
            if self._session:
                self._session.close()
            self.close()

    async def _process_msg_login(self, msg):
        if self._session:
            await self._session.async_close()
            self._session = None

        user = self._authenticate(msg['name'], msg['password'])
        if not user:
            await self._set_state(None, [], 'auth_fail', self._initial_view)
            return

        await self._set_state(user['name'], user['roles'], 'login',
                              user['view'])

        self._session = await _create_session(self._conn, user['name'],
                                              user['roles'], self._adapters)

    async def _process_msg_logout(self, msg):
        if self._session:
            await self._session.async_close()
            self._session = None

        await self._set_state(None, [], 'logout', self._initial_view)

    async def _process_msg_adapter(self, msg):
        if not self._session:
            return

        adapter_client = self._session.adapter_clients.get(msg['name'])
        if not adapter_client:
            return

        adapter_client.receive_queue.put_nowait(msg['data'])

    async def _set_state(self, user, roles, reason, view_name):
        view = await self._views.get(view_name) if view_name else None
        self._conn.set_local_data({})
        await self._conn.flush_local_data()
        await self._conn.send({'type': 'state',
                               'user': user,
                               'roles': roles,
                               'reason': reason,
                               'view': view.data if view else None,
                               'conf': view.conf if view else None})

    def _authenticate(self, name, password):
        user = self._users.get(name)
        if not user:
            return

        password = bytes.fromhex(password)
        user_salt = bytes.fromhex(user['password']['salt'])
        user_hash = bytes.fromhex(user['password']['hash'])

        h = hashlib.sha256()
        h.update(user_salt)
        h.update(password)

        if h.digest() != user_hash:
            return

        return user


async def _create_session(conn, user, roles, adapters):
    session = _Session()
    session._conn = conn
    session._async_group = conn.async_group.create_subgroup()
    session._adapter_clients = {}

    for name, adapter in adapters.items():
        adapter_client = AdapterSessionClient(
            session.async_group.create_subgroup(), name, conn, user, roles)
        session._bind_resource(adapter_client)

        adapter_session = await adapter.create_session(adapter_client)
        session._bind_resource(adapter_session)

        session._adapter_clients[name] = adapter_client

    return session


class _Session(aio.Resource):

    @property
    def async_group(self):
        return self._async_group

    @property
    def adapter_clients(self):
        return self._adapter_clients

    def _bind_resource(self, resource):
        self._async_group.spawn(aio.call_on_cancel, resource.async_close)
        self._async_group.spawn(aio.call_on_done, resource.wait_closing(),
                                self.close)


class AdapterSessionClient(common.AdapterSessionClient):

    def __init__(self, async_group, name, conn, user, roles):
        self._name = name
        self._conn = conn
        self._user = user
        self._roles = roles
        self._remote_data = None
        self._change_cbs = util.CallbackRegistry()
        self._receive_queue = aio.Queue()
        self._async_group = aio.Group()
        self._async_group.spawn(self._client_loop)

    @property
    def async_group(self):
        return self._async_group

    @property
    def receive_queue(self):
        return self._receive_queue

    @property
    def user(self):
        return self._user

    @property
    def roles(self):
        return self._roles

    @property
    def local_data(self):
        return self._conn.local_data.get(self._name)

    @property
    def remote_data(self):
        return self._remote_data

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    def set_local_data(self, data):
        if not self.is_open:
            raise Exception('adapter session client not open')

        local_data = dict(self._conn.local_data or {})
        local_data[self._name] = data
        self._conn.set_local_data(local_data)

    async def send(self, msg):
        await self.async_group.spawn(self._conn.send, {'type': 'adapter',
                                                       'name': self._name,
                                                       'data': msg})

    async def receive(self):
        try:
            return await self._receive_queue.get()

        except aio.QueueClosedError:
            raise ConnectionError()

    async def _client_loop(self):
        changes = aio.Queue()

        def on_change():
            remote_data = (self._conn.remote_data
                           if isinstance(self._conn.remote_data, dict)
                           else {})
            changes.put_nowait(remote_data.get(self._name))

        try:
            with self._conn.register_change_cb(on_change):
                on_change()

                while True:
                    remote_data = await changes.get()
                    if json.equals(remote_data, self._remote_data):
                        continue

                    self._remote_data = remote_data
                    self._change_cbs.notify()

        except Exception as e:
            mlog.error("client loop error: %s", e, exc_info=e)

        finally:
            self.close()
            self._receive_queue.close()
