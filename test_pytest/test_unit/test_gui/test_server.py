import asyncio
import contextlib
import hashlib
import pytest

import hat.gui.server
import hat.juggler

import test_unit.test_gui.mock
from test_unit.test_gui import common


def conf(ui_port, roles=[], users=[]):
    return {'address': f'http://localhost:{ui_port}',
            'initial_view': 'initial_view',
            'roles': roles,
            'users': users}


async def juggler_next_state(conn):
    wait_future = asyncio.Future()
    with conn.register_change_cb(lambda: wait_future.set_result(True)):
        await asyncio.wait_for(wait_future, 2)
    return conn.remote_data


def sha256_hexstr(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def user_conf(username, password, salt, roles):
    salt = salt.encode('utf-8').hex()
    m = hashlib.sha256(bytes.fromhex(salt))
    m.update(sha256_hexstr(password).encode('utf-8'))
    return {'name': username,
            'password': {'hash': m.hexdigest(),
                         'salt': salt},
            'roles': roles}


@pytest.fixture
def ui_static_files(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    with open(tmp_path / 'index.html', 'w') as f:
        f.write("""<!DOCTYPE html><head></head><body></body>""")
    return tmp_path


@pytest.fixture
def default_view_descriptors():
    return [
        common.FileDescriptor(
            relative_path='default.txt',
            serialization_method=common.SerializationMethod.TEXT,
            content='This is the default view')]


@pytest.fixture
def server_factory(view_factory, default_view_descriptors,
                   view_manager_factory, ui_static_files):

    @contextlib.asynccontextmanager
    async def factory(conf, adapters, view_manager=None):
        if view_manager is None:
            view_conf = [view_factory('initial_view',
                                      default_view_descriptors)]
            view_manager = await view_manager_factory(view_conf)
        server = await hat.gui.server.create(conf, ui_static_files, adapters,
                                             view_manager)
        yield server
        await server.async_close()

    return factory


@pytest.mark.asyncio
async def test_login_success(unused_tcp_port, server_factory):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'initial_view',
                               'adapters': []}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1'])])
    async with server_factory(server_conf, {}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')

        # juggler initial message
        await conn.receive()

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        state_message = await conn.receive()
        assert state_message['type'] == 'state'
        assert state_message['reason'] == 'login'
        assert state_message['user'] == 'user1'
        assert state_message['roles'] == ['role1']


@pytest.mark.asyncio
async def test_login_fail(unused_tcp_port, server_factory):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'initial_view',
                               'adapters': []}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1'])])
    async with server_factory(server_conf, {}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')

        # juggler initial message
        await conn.receive()

        await conn.send({'type': 'login',
                         'name': 'incorrect',
                         'password': sha256_hexstr('pass1')})
        state_message = await conn.receive()
        assert state_message['type'] == 'state'
        assert state_message['reason'] == 'auth_fail'
        assert state_message['user'] is None
        assert state_message['roles'] == []

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('incorrect')})
        state_message = await conn.receive()
        assert state_message['type'] == 'state'
        assert state_message['reason'] == 'auth_fail'
        assert state_message['user'] is None
        assert state_message['roles'] == []


@pytest.mark.asyncio
async def test_two_logins(unused_tcp_port, server_factory):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'initial_view',
                               'adapters': []}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1']),
                              user_conf('user2', 'pass2', 'salt2', ['role1'])])
    async with server_factory(server_conf, {}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')

        # juggler initial message
        await conn.receive()

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        # login confirmation
        await conn.receive()

        await conn.send({'type': 'login',
                         'name': 'user2',
                         'password': sha256_hexstr('pass2')})
        message = await conn.receive()
        assert message['type'] == 'state'
        assert message['reason'] == 'login'
        assert message['user'] == 'user2'
        assert message['roles'] == ['role1']


@pytest.mark.asyncio
async def test_two_logins_second_fail(unused_tcp_port, server_factory):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'initial_view',
                               'adapters': []}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1']),
                              user_conf('user2', 'pass2', 'salt2', ['role1'])])
    async with server_factory(server_conf, {}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')

        # juggler initial message
        await conn.receive()

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        # login confirmation
        await conn.receive()

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('incorrect')})
        message = await conn.receive()
        assert message['type'] == 'state'
        assert message['reason'] == 'auth_fail'
        assert message['user'] is None
        assert message['roles'] == []


@pytest.mark.asyncio
async def test_logout(unused_tcp_port, server_factory):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'initial_view',
                               'adapters': []}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1'])])
    async with server_factory(server_conf, {}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')

        # juggler initial message
        await conn.receive()

        await conn.send({'type': 'logout'})
        state_message = await conn.receive()
        assert state_message['type'] == 'state'
        assert state_message['reason'] == 'logout'
        assert state_message['user'] is None
        assert state_message['roles'] == []

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        # login confirm message
        await conn.receive()

        await conn.send({'type': 'logout'})
        state_message = await conn.receive()
        assert state_message['type'] == 'state'
        assert state_message['reason'] == 'logout'
        assert state_message['user'] is None
        assert state_message['roles'] == []


@pytest.mark.asyncio
async def test_view(unused_tcp_port, view_factory, default_view_descriptors,
                    view_manager_factory, server_factory):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'role1_view',
                               'adapters': []},
                              {'name': 'role2',
                               'view': 'role2_view',
                               'adapters': []}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1']),
                              user_conf('user2', 'pass2', 'salt2', ['role2'])])

    role1_descriptors = [
        common.FileDescriptor(
            relative_path='user1.txt',
            serialization_method=common.SerializationMethod.TEXT,
            content='User1 view')]
    role2_descriptors = [common.FileDescriptor(
            relative_path='user2.txt',
            serialization_method=common.SerializationMethod.TEXT,
            content='User2 view')]
    views_conf = [
        view_factory('initial_view', default_view_descriptors),
        view_factory('role1_view', role1_descriptors, conf={'key': 'value'}),
        view_factory('role2_view', role2_descriptors, conf={'key': 'value'})]
    view_manager = await view_manager_factory(views_conf)

    async with server_factory(server_conf, {}, view_manager):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')

        state_message = await conn.receive()
        assert state_message['type'] == 'state'
        assert state_message['conf'] is None
        view_state = state_message['view']
        for descriptor in default_view_descriptors:
            assert descriptor.relative_path in view_state
            assert descriptor.content == view_state[descriptor.relative_path]

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        state_message = await conn.receive()
        assert state_message['type'] == 'state'
        assert state_message['conf'] == {'key': 'value'}
        view_state = state_message['view']
        for descriptor in role1_descriptors:
            assert descriptor.relative_path in view_state
            assert descriptor.content == view_state[descriptor.relative_path]
        for descriptor in role2_descriptors:
            assert descriptor.relative_path not in view_state

        await conn.send({'type': 'login',
                         'name': 'user2',
                         'password': sha256_hexstr('pass2')})
        state_message = await conn.receive()
        assert state_message['type'] == 'state'
        assert state_message['conf'] == {'key': 'value'}
        view_state = state_message['view']
        for descriptor in role2_descriptors:
            assert descriptor.relative_path in view_state
            assert descriptor.content == view_state[descriptor.relative_path]
        for descriptor in role1_descriptors:
            assert descriptor.relative_path not in view_state

        await conn.send({'type': 'logout'})
        state_message = await conn.receive()
        assert state_message['type'] == 'state'
        assert state_message['conf'] is None
        view_state = state_message['view']
        for descriptor in default_view_descriptors:
            assert descriptor.relative_path in view_state
            assert descriptor.content == view_state[descriptor.relative_path]


@pytest.mark.asyncio
async def test_user_noroles(unused_tcp_port, server_factory,
                            default_view_descriptors):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[],
                       users=[user_conf('user1', 'pass1', 'salt1', [])])
    async with server_factory(server_conf, {}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')

        # juggler initial message
        await conn.receive()

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        while conn.remote_data != {}:
            await asyncio.sleep(0.1)

        state_message = await conn.receive()
        assert state_message['type'] == 'state'
        assert state_message['reason'] == 'internal_error'
        assert state_message['user'] is None
        assert state_message['roles'] == []
        assert state_message['conf'] is None
        view_state = state_message['view']
        for descriptor in default_view_descriptors:
            assert descriptor.relative_path in view_state
            assert descriptor.content == view_state[descriptor.relative_path]


@pytest.mark.asyncio
async def test_adapter_session_created(unused_tcp_port, server_factory):
    ui_port = unused_tcp_port
    user1_roles = [{'name': 'role1',
                    'view': 'initial_view',
                    'adapters': ['mock']}]
    server_conf = conf(ui_port,
                       roles=user1_roles,
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1'])])

    adapter = await test_unit.test_gui.mock.create(None, None)

    async with server_factory(server_conf, {'mock': adapter}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')
        state_message = await conn.receive()
        assert state_message['user'] is None

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        state_message = await conn.receive()
        assert state_message['user'] == 'user1'

        while len(adapter.sessions) != 1:
            await asyncio.sleep(0.1)
        client = adapter.sessions[0].session_client

        assert client.user == 'user1'
        assert client.roles == ['role1']

        conn2 = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')
        state_message = await conn2.receive()
        assert state_message['user'] is None

        await conn2.send({'type': 'login',
                          'name': 'user1',
                          'password': sha256_hexstr('pass1')})
        state_message = await conn2.receive()
        assert state_message['user'] == 'user1'

        while len(adapter.sessions) != 2:
            await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_adapter_session_adapter_msg(unused_tcp_port, server_factory):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'initial_view',
                               'adapters': ['mock']}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1'])])

    adapter = await test_unit.test_gui.mock.create(None, None)

    async with server_factory(server_conf, {'mock': adapter}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')
        state_message = await conn.receive()
        assert state_message['user'] is None

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        state_message = await conn.receive()
        assert state_message['user'] == 'user1'

        while len(adapter.sessions) != 1:
            await asyncio.sleep(0.1)
        client = adapter.sessions[0].session_client

        msg_data = {'key': 'value'}
        await conn.send({'type': 'adapter',
                         'name': 'mock',
                         'data': msg_data})
        received = await client.receive()
        assert received == msg_data

        msg_data = 'JSON serializable data'
        await client.send(msg_data)
        received = await conn.receive()
        assert received == {'type': 'adapter',
                            'name': 'mock',
                            'data': msg_data}


@pytest.mark.asyncio
async def test_close_juggler(unused_tcp_port, server_factory):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'initial_view',
                               'adapters': ['mock']}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1'])])

    adapter = await test_unit.test_gui.mock.create(None, None)

    async with server_factory(server_conf, {'mock': adapter}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')
        state_message = await conn.receive()
        assert state_message['user'] is None

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        state_message = await conn.receive()
        assert state_message['user'] == 'user1'

        while len(adapter.sessions) != 1:
            await asyncio.sleep(0.1)

        await conn.async_close()
        await adapter.sessions[0].closed


@pytest.mark.asyncio
async def test_adapter_session_juggler_data(unused_tcp_port, server_factory):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'initial_view',
                               'adapters': ['mock']}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1'])])

    adapter = await test_unit.test_gui.mock.create(None, None)

    async with server_factory(server_conf, {'mock': adapter}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')
        assert conn.remote_data is None
        state_message = await conn.receive()
        assert state_message['user'] is None

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        state_message = await conn.receive()
        assert state_message['user'] == 'user1'

        while len(adapter.sessions) != 1:
            await asyncio.sleep(0.1)
        client = adapter.sessions[0].session_client
        assert conn.remote_data == {}
        assert client.local_data is None

        wait_remote = asyncio.Future()
        with conn.register_change_cb(lambda: wait_remote.set_result(True)):
            client.set_local_data(0)
            await wait_remote
        assert client.local_data == 0
        assert conn.remote_data == {'mock': 0}

        wait_remote = asyncio.Future()
        with client.register_change_cb(lambda: wait_remote.set_result(True)):
            conn.set_local_data({'mock': 1})
            await wait_remote
        assert client.remote_data == 1

        wait_remote = asyncio.Future()
        with conn.register_change_cb(lambda: wait_remote.set_result(True)):
            client.set_local_data(False)
            await wait_remote
        assert conn.remote_data == {'mock': False}


@pytest.mark.asyncio
async def test_notify_called_when_relevant(unused_tcp_port, server_factory):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'initial_view',
                               'adapters': ['mock1', 'mock2']}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1'])])

    adapter1 = await test_unit.test_gui.mock.create(None, None)
    adapter2 = await test_unit.test_gui.mock.create(None, None)

    async with server_factory(server_conf, {'mock1': adapter1,
                                            'mock2': adapter2}):
        conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')
        assert conn.remote_data is None
        state_message = await conn.receive()
        assert state_message['user'] is None

        await conn.send({'type': 'login',
                         'name': 'user1',
                         'password': sha256_hexstr('pass1')})
        state_message = await conn.receive()
        assert state_message['user'] == 'user1'

        while len(adapter1.sessions) != 1:
            await asyncio.sleep(0.1)
        client1 = adapter1.sessions[0].session_client
        assert conn.remote_data == {}

        while len(adapter2.sessions) != 1:
            await asyncio.sleep(0.1)
        client2 = adapter2.sessions[0].session_client
        assert conn.remote_data == {}

        wait_mock1 = asyncio.Future()
        wait_mock2 = asyncio.Future()
        with client2.register_change_cb(lambda: wait_mock2.set_result(True)):
            with client1.register_change_cb(
                    lambda: wait_mock1.set_result(True)):
                conn.set_local_data({'mock1': 1})
                await wait_mock1
            assert client1.remote_data == 1
            assert not wait_mock2.done()


@pytest.mark.asyncio
async def test_server_shutdown(unused_tcp_port, server_factory, monkeypatch):
    ui_port = unused_tcp_port
    server_conf = conf(ui_port,
                       roles=[{'name': 'role1',
                               'view': 'initial_view',
                               'adapters': ['mock']}],
                       users=[user_conf('user1', 'pass1', 'salt1', ['role1'])])

    adapter = await test_unit.test_gui.mock.create(None, None)
    sessions = []

    create_session_default = hat.gui.server.create_session

    async def create_session_wrap(*args):
        session = await create_session_default(*args)
        sessions.append(session)
        return session

    with monkeypatch.context() as ctx:
        ctx.setattr(hat.gui.server, 'create_session', create_session_wrap)
        async with server_factory(server_conf, {'mock': adapter}):
            conn = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')
            state_message = await conn.receive()
            assert state_message['user'] is None

            await conn.send({'type': 'login',
                             'name': 'user1',
                             'password': sha256_hexstr('pass1')})
            state_message = await conn.receive()
            assert state_message['user'] == 'user1'

            while len(adapter.sessions) != 1:
                await asyncio.sleep(0.1)

            conn2 = await hat.juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')
            state_message = await conn2.receive()
            assert state_message['user'] is None

            await conn2.send({'type': 'login',
                              'name': 'user1',
                              'password': sha256_hexstr('pass1')})
            state_message = await conn2.receive()
            assert state_message['user'] == 'user1'

            while len(adapter.sessions) != 2:
                await asyncio.sleep(0.1)

    await conn.closed
    await conn2.closed
    await asyncio.wait([session.closed for session in sessions])
    await asyncio.wait([session.closed for session in adapter.sessions])
    assert not adapter.closed.done()
