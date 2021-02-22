import asyncio
import hashlib

import pytest

from hat import aio
from hat import juggler
from hat import util
from hat.gui import common
import hat.event.common
import hat.gui.server


pytestmark = pytest.mark.asyncio


@pytest.fixture
def ui_path(tmp_path):
    ui_path = tmp_path / 'ui'
    ui_path.mkdir(parents=True, exist_ok=True)
    return ui_path


@pytest.fixture
def ui_port():
    return util.get_unused_tcp_port()


@pytest.fixture
def ui_addr(ui_port):
    return f'http://127.0.0.1:{ui_port}'


@pytest.fixture
def ws_addr(ui_addr):
    return f'{ui_addr}/ws'


@pytest.fixture
def patch_autoflush_delay(monkeypatch):
    monkeypatch.setattr(hat.gui.server, 'autoflush_delay', 0)


def get_password_conf(password, salt):
    password = password.encode()
    salt = salt.encode()
    h = hashlib.sha256()
    h.update(salt)
    h.update(hashlib.sha256(password).digest())
    return {'hash': h.hexdigest(),
            'salt': salt.hex()}


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


class Adapter(common.Adapter):

    def __init__(self):
        self._session_queue = aio.Queue()
        self._async_group = aio.Group()

    @property
    def async_group(self):
        return self._async_group

    @property
    def session_queue(self):
        return self._session_queue

    async def create_session(self, client):
        session = Session(client)
        self._session_queue.put_nowait(session)
        return session


class Session(aio.Resource):

    def __init__(self, client):
        self._client = client
        self._async_group = aio.Group()

    @property
    def async_group(self):
        return self._async_group

    @property
    def client(self):
        return self._client


class ViewManager(aio.Resource):

    def __init__(self, views):
        self._views = views
        self._async_group = aio.Group()

    @property
    def async_group(self):
        return self._async_group

    async def get(self, name):
        return self._views[name]


async def test_empty_server(ui_path, ui_addr, ws_addr):
    conf = {'address': ui_addr,
            'initial_view': None,
            'users': []}
    adapters = {}
    views = ViewManager({})
    server = await hat.gui.server.create_server(conf, ui_path, adapters, views)
    client = await juggler.connect(ws_addr, autoflush_delay=0)

    assert client.is_open
    assert server.is_open

    await client.async_close()
    await server.async_close()
    await views.async_close()


async def test_login(ui_path, ui_addr, ws_addr):
    conf = {'address': ui_addr,
            'initial_view': None,
            'users': [{'name': 'user',
                       'password': get_password_conf('pass', 'salt'),
                       'roles': ['a', 'b'],
                       'view': None}]}
    adapters = {}
    views = ViewManager({})
    server = await hat.gui.server.create_server(conf, ui_path, adapters, views)
    client = await juggler.connect(ws_addr, autoflush_delay=0)

    state = await client.receive()
    assert state == {'type': 'state',
                     'reason': 'init',
                     'user': None,
                     'roles': [],
                     'view': None,
                     'conf': None}

    await client.send({'type': 'login',
                       'name': 'abc',
                       'password': hash_password('bca')})

    state = await client.receive()
    assert state == {'type': 'state',
                     'reason': 'auth_fail',
                     'user': None,
                     'roles': [],
                     'view': None,
                     'conf': None}

    await client.send({'type': 'login',
                       'name': 'user',
                       'password': hash_password('pass')})
    state = await client.receive()
    assert state == {'type': 'state',
                     'reason': 'login',
                     'user': 'user',
                     'roles': ['a', 'b'],
                     'view': None,
                     'conf': None}

    await client.send({'type': 'logout'})
    state = await client.receive()
    assert state == {'type': 'state',
                     'reason': 'logout',
                     'user': None,
                     'roles': [],
                     'view': None,
                     'conf': None}

    await client.async_close()
    await server.async_close()
    await views.async_close()


async def test_adapter_session(ui_path, ui_addr, ws_addr):
    conf = {'address': ui_addr,
            'initial_view': None,
            'users': [{'name': 'user',
                       'password': get_password_conf('pass', 'salt'),
                       'roles': [],
                       'view': None}]}
    adapter = Adapter()
    adapters = {'adapter': adapter}
    views = ViewManager({})
    server = await hat.gui.server.create_server(conf, ui_path, adapters, views)
    client = await juggler.connect(ws_addr, autoflush_delay=0)

    state = await client.receive()
    assert state['reason'] == 'init'

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(adapter.session_queue.get(), 0.001)

    await client.send({'type': 'login',
                       'name': 'user',
                       'password': hash_password('pass')})
    state = await client.receive()
    assert state['reason'] == 'login'

    session = await adapter.session_queue.get()

    assert session.is_open

    await client.send({'type': 'logout'})
    state = await client.receive()
    assert state['reason'] == 'logout'

    assert not session.is_open

    await client.async_close()
    await server.async_close()
    await views.async_close()


async def test_adapter_send_receive(ui_path, ui_addr, ws_addr):
    conf = {'address': ui_addr,
            'initial_view': None,
            'users': [{'name': 'user',
                       'password': get_password_conf('pass', 'salt'),
                       'roles': [],
                       'view': None}]}
    adapter = Adapter()
    adapters = {'adapter': adapter}
    views = ViewManager({})
    server = await hat.gui.server.create_server(conf, ui_path, adapters, views)
    client = await juggler.connect(ws_addr, autoflush_delay=0)
    await client.receive()
    await client.send({'type': 'login',
                       'name': 'user',
                       'password': hash_password('pass')})
    await client.receive()
    session = await adapter.session_queue.get()

    await session.client.send('abc')
    msg = await client.receive()
    assert msg == {'type': 'adapter',
                   'name': 'adapter',
                   'data': 'abc'}

    await client.send({'type': 'adapter',
                       'name': 'adapter',
                       'data': 123})
    msg = await session.client.receive()
    assert msg == 123

    await client.async_close()
    await server.async_close()
    await views.async_close()


async def test_adapter_remote_data(ui_path, ui_addr, ws_addr,
                                   patch_autoflush_delay):
    conf = {'address': ui_addr,
            'initial_view': None,
            'users': [{'name': 'user',
                       'password': get_password_conf('pass', 'salt'),
                       'roles': [],
                       'view': None}]}
    adapter = Adapter()
    adapters = {'adapter': adapter}
    views = ViewManager({})
    server = await hat.gui.server.create_server(conf, ui_path, adapters, views)
    client = await juggler.connect(ws_addr, autoflush_delay=0)
    await client.send({'type': 'login',
                       'name': 'user',
                       'password': hash_password('pass')})
    session = await adapter.session_queue.get()

    assert session.client.remote_data is None
    assert client.remote_data.get('adapter') is None

    frontend_data_queue = aio.Queue()
    session.client.register_change_cb(
        lambda: frontend_data_queue.put_nowait(session.client.remote_data))

    backend_data_queue = aio.Queue()
    client.register_change_cb(
        lambda: backend_data_queue.put_nowait(client.remote_data))

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(frontend_data_queue.get(), 0.001)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(backend_data_queue.get(), 0.001)

    client.set_local_data({'adapter': 123})
    data = await frontend_data_queue.get()
    assert data == 123

    session.client.set_local_data('abc')
    data = await backend_data_queue.get()
    assert data == {'adapter': 'abc'}

    await client.async_close()
    await server.async_close()
    await views.async_close()


# TODO: test view
