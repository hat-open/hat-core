import pytest
import yaml
import urllib.parse
import subprocess
import psutil
import sys
import signal
import time
import hashlib
import collections
import asyncio
import random
import secrets
import string

from hat import aio
from hat import json
from hat import juggler
from hat import util
import hat.event.client
import hat.event.common

View = collections.namedtuple('View',
                              ['name', 'path', 'file_data', 'conf_path'])

initial_view = View(name='init', path='views/init',
                    file_data={'init.txt': 'this is login view'},
                    conf_path=None)


client_receive_timeout = 0.1
listens_port_timeout = 2


class Process:

    def __init__(self, cmd, stdout=None, ignore_stderr=False):
        creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP
                         if sys.platform == 'win32' else 0)
        self._p = psutil.Popen(
            cmd, creationflags=creationflags, stdout=stdout,
            stderr=subprocess.DEVNULL if ignore_stderr else None)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if not self.is_running():
            return
        self._p.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == 'win32'
                            else signal.SIGTERM)

    def wait_until_closed(self, wait_timeout=5):
        self._p.wait(wait_timeout)

    def close_and_wait_or_kill(self, wait_timeout=5):
        self.close()
        try:
            self._p.wait(wait_timeout)
        except psutil.TimeoutExpired:
            self._p.kill()

    def is_running(self):
        return self._p.is_running() and self._p.status() != 'zombie'

    def listens_on(self, local_port):
        return bool(util.first(self._p.connections(),
                               lambda i: i.status == 'LISTEN' and
                               i.laddr.port == local_port))

    def connected_to(self, port):
        return bool(util.first(self._p.connections(),
                               lambda i: i.status == 'ESTABLISHED' and
                               i.raddr.port == port))


def wait_until(fn, *args, timeout=5):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if fn(*args):
            return
        time.sleep(0.01)
    raise TimeoutError()


def views_conf_from_views(views, path, init=None):
    init = init if init else initial_view
    views.append(init)
    conf = []
    for view in views:
        view_path = path / view.path
        if not view_path.exists():
            view_path.mkdir(parents=True)
        for filename, data in view.file_data.items():
            with open(view_path / filename, 'w', encoding='utf-8') as f:
                f.write(data)
        conf.append({'name': view.name,
                     'view_path': str(view_path),
                     'conf_path': (str(path / view.conf_path)
                                   if view.conf_path else None)})
    return conf


async def get_first_event(client, fn=lambda _: True):
    while True:
        events = await client.receive()
        for e in events:
            if fn(e):
                return e


async def register_event(client, event_type, json_payload_data):
    await client.register_with_response(
        [hat.event.common.RegisterEvent(
            event_type=event_type,
            source_timestamp=None,
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.JSON,
                data=json_payload_data))])


async def create_client(gui_conf, user_conf):
    client = Client()
    ui_port = urllib.parse.urlparse(gui_conf['address']).port
    client._conn = await juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')
    client._user_conf = user_conf
    return client


class Client(aio.Resource):

    @property
    def async_group(self):
        return self._conn.async_group

    @property
    def server_state(self):
        return self._conn.remote_data

    @property
    def state(self):
        return self._conn.local_data

    def set_local_data(self, data):
        self._conn.set_local_data(data)

    def register_change_cb(self, cb):
        return self._conn.register_change_cb(cb)

    async def login(self, name=None, password=None):
        name = name or self._user_conf['name']
        password = (password.encode().hex() if password
                    else self._user_conf['password']['pass'])
        await self._conn.send({'type': 'login',
                               'name': name,
                               'password': password})

    async def logout(self):
        await self._conn.send({'type': 'logout'})

    async def send(self, msg):
        await self._conn.send(msg)

    async def receive(self):
        return await self._conn.receive()


@pytest.fixture
@pytest.mark.asyncio
async def event_client(event_address):
    client = await hat.event.client.connect(
        event_address,
        subscriptions=[('*')])

    yield client

    await client.async_close()


@pytest.fixture
def monitor_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def monitor_address(monitor_port):
    return f'tcp+sbs://127.0.0.1:{monitor_port}'


@pytest.fixture
def monitor_conf(monitor_address, unused_tcp_port_factory):
    return {'type': 'monitor',
            'log': {'version': 1},
            'server': {
                'address': monitor_address,
                'default_rank': 1},
            'master': {
                'address': f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}',
                'default_algorithm': 'BLESS_ONE',
                'group_algorithms': {}},
            'slave': {
                'parents': []},
            'ui': {
                'address': f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}'}}


@pytest.fixture
def monitor_process(tmp_path, monitor_conf, monitor_port):
    conf_path = tmp_path / 'monitor.yaml'
    with open(conf_path, 'w', encoding='utf-8') as f:
        yaml.dump(monitor_conf, f)
    args = ['python', '-m', 'hat.monitor.server',
            '--conf', str(conf_path),
            '--ui-path', str(tmp_path)]
    with Process(args) as p:
        wait_until(p.listens_on, monitor_port, timeout=listens_port_timeout)
        yield p


@pytest.fixture
def event_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def event_address(event_port):
    return f'tcp+sbs://127.0.0.1:{event_port}'


@pytest.fixture
def event_conf(event_address, monitor_address, tmp_path):
    return {'type': 'event',
            'log': {'version': 1},
            'monitor': {'name': 'es1',
                        'group': 'es',
                        'monitor_address': monitor_address,
                        'component_address': event_address},
            'backend_engine': {'server_id': 1,
                               'backend':
                                   {'module':
                                       'hat.event.server.backends.sqlite',
                                    'db_path': str(tmp_path / 'event.db'),
                                    'query_pool_size': 10}},
            'module_engine': {'modules': []},
            'communication': {'address': event_address}}


def run_event_server(conf_path, event_conf, ignore_stderr=False):
    conf_path = conf_path / 'event.yaml'
    with open(conf_path, 'w', encoding='utf-8') as f:
        yaml.dump(event_conf, f)

    proc = Process(['python', '-m', 'hat.event.server',
                    '--conf', str(conf_path)],
                   ignore_stderr=ignore_stderr)
    return proc


@pytest.fixture
def event_process(tmp_path, event_conf, event_port):
    p = run_event_server(tmp_path, event_conf)
    wait_until(p.listens_on, event_port, timeout=listens_port_timeout)

    yield p

    p.close_and_wait_or_kill()


@pytest.fixture
def gui_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


def generate_password():
    password = ('').join(random.choices(string.ascii_letters + string.digits,
                                        k=8))
    password_hashed = hashlib.sha256(password.encode('utf-8')).digest()
    salt = secrets.token_bytes(16)
    m = hashlib.sha256(salt)
    m.update(password_hashed)
    return {'hash': m.hexdigest(), 'salt': salt.hex(),
            'pass': password_hashed.hex()}


@pytest.fixture
def gui_conf(monitor_address, event_address, gui_port):
    return {
        'type': 'gui',
        'log': {'version': 1},
        'monitor': {'name': 'gui',
                    'group': 'guis',
                    'monitor_address': monitor_address,
                    'component_address': event_address},
        'event_server_group': 'es',
        'adapters': [],
        'views': [],
        'address': f'http://localhost:{gui_port}',
        'initial_view': 'init',
        'users': []}


def add_adapters_users_roles(gui_conf, views_path, no_users_roles, views=None,
                             adapters_per_role=1):
    gui_conf['adapters'] = [{'name': f'adapter{i*adapters_per_role + j + 1}',
                             'module': 'test_sys.test_gui.mock_adapter'}
                            for j in range(adapters_per_role)
                            for i in range(no_users_roles)]
    gui_conf['users'] = [
        {'name': f'user{i + 1}',
         'password': generate_password(),
         'view': f'view{i + 1}',
         'roles': [f'role{j + 1}' for j in range(i, no_users_roles)]}
        for i in range(no_users_roles)]
    views = views if views else [
        View(name=f'view{i + 1}', path=f'views/view{i + 1}',
             file_data={f'view{i + 1}.txt': f'this is view{i + 1}'},
             conf_path=None)
        for i in range(no_users_roles)]
    gui_conf['views'] = views_conf_from_views(views, views_path)
    return gui_conf


def run_gui_nowait(conf_path, ui_path, gui_conf, ignore_stderr=False):
    with open(conf_path, 'w', encoding='utf-8') as f:
        yaml.dump(gui_conf, f)
    args = ['python', '-m', 'hat.gui',
            '--conf', str(conf_path),
            '--ui-path', ui_path]
    return Process(args, ignore_stderr=ignore_stderr)


@pytest.fixture
def run_gui(tmp_path, monitor_process, event_process, gui_conf, gui_port):

    def wrapper(gui_conf, ignore_stderr=False):
        p = run_gui_nowait(conf_path=tmp_path / 'gui.yaml',
                           ui_path=str(tmp_path), gui_conf=gui_conf,
                           ignore_stderr=ignore_stderr)
        wait_until(p.listens_on, gui_port, timeout=listens_port_timeout)
        return p

    return wrapper


@pytest.fixture
def run_gui_without_event(tmp_path, monitor_process, gui_conf, gui_port):

    def wrapper(gui_conf, ignore_stderr=False):
        p = run_gui_nowait(conf_path=tmp_path / 'gui.yaml',
                           ui_path=str(tmp_path), gui_conf=gui_conf,
                           ignore_stderr=ignore_stderr)
        wait_until(p.is_running, timeout=listens_port_timeout)
        return p

    return wrapper


@pytest.mark.asyncio
async def test_monitor_close(tmp_path, run_gui_without_event, gui_conf,
                             monitor_process, monitor_port):

    gui_process = run_gui_without_event(gui_conf, ignore_stderr=True)

    monitor_process.close()

    gui_process.wait_until_closed()
    assert not gui_process.is_running()

    gui_process = run_gui_without_event(gui_conf, ignore_stderr=True)
    gui_process.wait_until_closed()
    assert not gui_process.is_running()


@pytest.mark.asyncio
async def test_event_close(tmp_path, run_gui_without_event, gui_conf, gui_port,
                           event_conf, event_port, monitor_process):
    gui_process = run_gui_without_event(gui_conf)
    assert gui_process.is_running()
    assert not gui_process.listens_on(gui_port)

    event_process = run_event_server(tmp_path, event_conf)
    wait_until(gui_process.connected_to, event_port)
    wait_until(gui_process.listens_on, gui_port)

    event_process.close_and_wait_or_kill()

    with pytest.raises(psutil.TimeoutExpired):
        gui_process.wait_until_closed(1)
    assert gui_process.is_running()
    assert not gui_process.listens_on(gui_port)
    assert not gui_process.connected_to(event_port)

    event_process = run_event_server(tmp_path, event_conf)
    assert gui_process.is_running()
    wait_until(gui_process.connected_to, event_port)
    wait_until(gui_process.listens_on, gui_port)

    gui_process.close_and_wait_or_kill()
    event_process.close_and_wait_or_kill()


@pytest.mark.asyncio
async def test_user_login(run_gui, gui_conf, gui_port,
                          tmp_path, event_process):
    gui_conf = add_adapters_users_roles(gui_conf, tmp_path, no_users_roles=1)
    view_name = gui_conf['views'][0]['name']
    gui_process = run_gui(gui_conf)
    wait_until(gui_process.listens_on, gui_port)
    user_conf = gui_conf['users'][0]
    client = await create_client(gui_conf, user_conf)

    msg_initial = {'type': 'state',
                   'reason': 'init',
                   'user': None,
                   'roles': [],
                   'view': initial_view.file_data,
                   'conf': None}
    msg_login = {'type': 'state',
                 'reason': 'login',
                 'user': user_conf['name'],
                 'roles': user_conf['roles'],
                 'view': {f'{view_name}.txt':
                          f'this is {view_name}'},
                 'conf': None}
    msg_auth_fail = dict(msg_initial, reason='auth_fail')
    msg_logout = dict(msg_initial, reason='logout')

    # inital message
    assert await client.receive() == msg_initial

    # login failed
    await client.login(password='abc')
    assert await client.receive() == msg_auth_fail
    await client.login(name='xy')
    assert await client.receive() == msg_auth_fail
    await client.login(name='123', password='456')
    assert await client.receive() == msg_auth_fail

    # login success
    await client.login()
    assert await client.receive() == msg_login

    # login success again
    await client.login()
    assert await client.receive() == msg_login

    # login failed while logged-in
    await client.login(name='bla')
    assert await client.receive() == msg_auth_fail

    await client.logout()
    assert await client.receive() == msg_logout

    gui_process.close_and_wait_or_kill()
    await client.async_close()


@pytest.mark.asyncio
async def test_adapter_msg(run_gui, gui_conf, tmp_path,
                           event_process, event_client):
    gui_conf = add_adapters_users_roles(gui_conf, tmp_path, no_users_roles=1)
    gui_process = run_gui(gui_conf)

    user_conf = gui_conf['users'][0]
    client = await create_client(gui_conf, user_conf)
    await client.receive()

    # no data before login
    await register_event(event_client, ('a1', 'data'), {'abc': 1})
    with pytest.raises(asyncio.exceptions.TimeoutError):
        await asyncio.wait_for(client.receive(), client_receive_timeout)

    await client.login()
    await client.receive()

    # event server to client
    await register_event(event_client, ('a1', 'data'), {'abc': 1})
    assert await client.receive() == {'type': 'adapter',
                                      'name': 'adapter1',
                                      'data': {'abc': 1}}
    # MockAdapter not expected to get this event
    await register_event(event_client, ('a2', 'data'), {'def': 2})
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client.receive(), client_receive_timeout)

    # client to event server
    await client.send({'type': 'adapter',
                       'name': 'adapter1',
                       'data': {'xyz': 2}})
    event = await get_first_event(event_client,
                                  lambda e: e.event_type == ('a1', 'action'))
    assert event.payload.data == {'xyz': 2}
    # message sent to wrong adapter -> no new events
    await client.send({'type': 'adapter',
                       'name': 'adapter2',
                       'data': {'xyz': 3}})
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(event_client.receive(), client_receive_timeout)

    await client.async_close()
    gui_process.close_and_wait_or_kill()


@pytest.mark.asyncio
async def test_adapter_state(run_gui, gui_conf, tmp_path,
                             event_process, event_client):
    gui_conf = add_adapters_users_roles(gui_conf, tmp_path, no_users_roles=1)
    gui_process = run_gui(gui_conf)

    user_conf = gui_conf['users'][0]
    client = await create_client(gui_conf, user_conf)
    client_change_queue = aio.Queue()
    client.register_change_cb(lambda: client_change_queue.put_nowait(None))
    await client.receive()
    await client.login()
    await client.receive()

    # event server to client
    await register_event(event_client, ('a1', 'data'), {'abc': 1})
    await aio.first(client_change_queue, lambda _: client.server_state)
    assert client.server_state == {'adapter1': [{'abc': 1}]}

    # client to event server
    client.set_local_data({'adapter1': ['a', 'b', 'c']})
    event = await get_first_event(event_client,
                                  lambda e: e.event_type == ('a1', 'action'))
    assert event.payload.data == ['a', 'b', 'c']

    # data with wrong adapter name
    client.set_local_data({'adapter2': ['a', 'b', 'c']})
    event = await get_first_event(event_client,
                                  lambda e: e.event_type == ('a1', 'action'))
    assert event.payload.data is None

    await client.async_close()
    gui_process.close_and_wait_or_kill()


@pytest.mark.asyncio
async def test_event_to_adapters(run_gui, gui_conf, tmp_path,
                                 event_process, event_client):
    no_adapters = 10
    gui_conf = add_adapters_users_roles(gui_conf, tmp_path, no_users_roles=1,
                                        adapters_per_role=no_adapters)
    adapters = [i['name'] for i in gui_conf['adapters']]
    gui_process = run_gui(gui_conf)

    user_conf = gui_conf['users'][0]
    client = await create_client(gui_conf, user_conf)
    client_change_queue = aio.Queue()
    client.register_change_cb(lambda: client_change_queue.put_nowait(None))
    await client.receive()
    await client.login()
    await client.receive()
    await register_event(event_client, ('a1', 'data'), {'abc': 1})

    for adapter in adapters:
        assert await client.receive() == {'type': 'adapter',
                                          'name': adapter,
                                          'data': {'abc': 1}}
    await aio.first(client_change_queue,
                    lambda _: len(client.server_state) == no_adapters)
    assert client.server_state == {a: [{'abc': 1}] for a in adapters}

    await client.async_close()
    gui_process.close_and_wait_or_kill()


@pytest.mark.asyncio
async def test_invalid_message(run_gui, gui_conf, tmp_path,
                               event_process):
    invalid_msg = {'type': 'invalid',
                   'name': 'invalid_adapter',
                   'data': 'xx'}
    gui_conf = add_adapters_users_roles(gui_conf, tmp_path, no_users_roles=1)
    gui_process = run_gui(gui_conf)

    user_conf = gui_conf['users'][0]
    client = await create_client(gui_conf, user_conf)

    # invalid message before login
    await client.send(invalid_msg)
    await asyncio.sleep(0.01)
    with pytest.raises(ConnectionError):
        await client.login()
    assert client.is_closed

    # invalid message after login
    client = await create_client(gui_conf, user_conf)
    await client.receive()
    await client.login()
    msg = await client.receive()
    assert msg['user'] == 'user1'
    await client.send(invalid_msg)
    await asyncio.sleep(0.01)
    with pytest.raises(ConnectionError):
        await client.login()
    assert client.is_closed

    gui_process.close_and_wait_or_kill()


@pytest.mark.parametrize("no_users", [1, 3, 10])
@pytest.mark.asyncio
async def test_users_roles(tmp_path, run_gui, gui_conf,
                           event_process, event_client, no_users):
    gui_conf = add_adapters_users_roles(gui_conf, tmp_path, no_users,
                                        adapters_per_role=3)
    gui_process = run_gui(gui_conf)
    # create and login all clients
    clients = []
    for user_conf in gui_conf['users']:
        client = await create_client(gui_conf, user_conf)
        clients.append(client)
        await client.receive()
        await client.login()
        msg = await client.receive()
        assert msg['user'] == user_conf['name']
        assert msg['roles'] == user_conf['roles']
        assert msg['view'] == {f"{user_conf['view']}.txt":
                               f"this is {user_conf['view']}"}
    # event gets to all clients for each adapter
    await register_event(event_client, ('a1', 'data'), {'abc': 1})
    for client in clients:
        client_adapters = {i['name'] for i in gui_conf['adapters']}
        while client_adapters:
            msg = await client.receive()
            adapter_name = msg['name']
            assert adapter_name in client_adapters
            assert msg['data'] == {'abc': 1}
            client_adapters.remove(adapter_name)

    assert all(not client.is_closed for client in clients)

    for client in clients:
        await client.async_close()
    gui_process.close_and_wait_or_kill()


@pytest.mark.parametrize("conf_format", ['yaml', 'json', 'yml'])
@pytest.mark.asyncio
async def test_view_conf(tmp_path, run_gui, gui_conf, gui_port, event_process,
                         conf_format):

    schema = {"$schema": "http://json-schema.org/schema#",
              "id":  f"test://views/view1.{conf_format}#",
              "type": "object",
              "required": ['x', 'y'],
              "properties": {'x': {"type": 'number'},
                             'y': {"type": 'string'}}
              }
    view_conf = {"x": 2,
                 "y": 'a'}
    views = [View(name='view1', path='views/view1',
                  file_data={'view1': 'this is view1',
                             f'schema.{conf_format}': json.encode(schema),
                             f'conf.{conf_format}': json.encode(view_conf)},
                  conf_path=f'views/view1/conf.{conf_format}')]
    gui_conf = add_adapters_users_roles(gui_conf, tmp_path, no_users_roles=1,
                                        views=views)
    gui_process = run_gui(gui_conf)
    wait_until(gui_process.listens_on, gui_port)

    user_conf = gui_conf['users'][0]
    client = await create_client(gui_conf, user_conf)
    await client.receive()

    await client.login()
    msg = await client.receive()
    assert msg['user'] == 'user1'
    assert set(views[0].file_data.keys()) == set(msg['view'].keys())
    assert msg['view'][f'schema.{conf_format}'] == schema
    assert msg['view'][f'conf.{conf_format}'] == view_conf

    await client.async_close()
    gui_process.close_and_wait_or_kill()


@pytest.mark.asyncio
async def test_view_xml(tmp_path, run_gui, gui_conf, gui_port, event_process):
    xml = '''\
            <html>
                    <body>
                        <div id="first" class="c1 c2">
                            Banana
                        </div>
                        Orange
                        <br/>
                        <span id="second" style="color:green">
                            Watermelon
                        </span>
                    </body>
                </html>
            '''
    vt_exp = ['html',
              ['body',
               ['div#first.c1.c2',
                "Banana"
                ],
               "Orange",
               ['br'],
               ['span#second',
                {'attrs':
                    {'style': "color:green"}},
                "Watermelon"
                ]
               ]
              ]
    xml_stripped = ''.join(line.lstrip() for line in xml.split('\n'))
    views = [View(name='view1', path='views/view1',
                  file_data={'view1.xml': xml_stripped}, conf_path=None)]
    gui_conf = add_adapters_users_roles(gui_conf, tmp_path, no_users_roles=1,
                                        views=views)
    gui_process = run_gui(gui_conf)
    wait_until(gui_process.listens_on, gui_port)

    user_conf = gui_conf['users'][0]
    client = await create_client(gui_conf, user_conf)
    await client.receive()

    await client.login()
    msg = await client.receive()
    assert msg['user'] == 'user1'
    assert msg['view']['view1.xml'] == vt_exp

    await client.async_close()
    gui_process.close_and_wait_or_kill()


@pytest.mark.asyncio
async def test_adapter_close(run_gui, gui_conf, tmp_path,
                             event_process, event_client):
    gui_conf = add_adapters_users_roles(gui_conf, tmp_path, no_users_roles=1)
    gui_process = run_gui(gui_conf)
    user_conf = gui_conf['users'][0]
    client = await create_client(gui_conf, user_conf)
    await client.receive()
    await client.login()
    await client.receive()

    # this event results with MockAdapter closing
    await register_event(event_client, ('a1', 'kill'), None)

    # after adapter is closed, gui is expected to close
    gui_process.wait_until_closed()
    # juggler connection is closed
    with pytest.raises(ConnectionError):
        await client.receive()

    await client.async_close()
