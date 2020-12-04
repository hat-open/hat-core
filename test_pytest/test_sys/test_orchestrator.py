import time
import asyncio
import sys
import subprocess
import signal
import psutil
import pytest
import urllib

from hat import aio
from hat import json
from hat import juggler
from hat import util


no_change_delay = 1
ui_timeout = 0.25


Component = util.namedtuple(
    'Component',
    ['id', 'int'],
    ['name', 'str'],
    ['delay', 'float'],
    ['revive', 'bool'],
    ['status', 'str'])


async def create_client(address):
    ui_address = urllib.parse.urlparse(address)
    ws_address = 'ws://{}:{}/ws'.format(ui_address.hostname,
                                        ui_address.port)
    client = Client()
    client._conn = await juggler.connect(ws_address)
    client._async_group = aio.Group()
    return client


class Client:

    @property
    def closed(self):
        return self._conn.closed

    @property
    def components(self):
        if not self._conn.remote_data:
            return []
        return [Component(
            id=i['id'],
            name=i['name'],
            delay=i['delay'],
            revive=i['revive'],
            status=i['status']) for i in self._conn.remote_data['components']]

    def register_components_change_cb(self, cb):
        return self._conn.register_change_cb(cb)

    async def async_close(self):
        await self._async_group.async_close()
        await self._conn.async_close()

    def start(self, component_id):
        self._async_group.spawn(self._conn.send,
                                {'type': 'start',
                                 'payload': {'id': component_id}})

    def stop(self, component_id):
        self._async_group.spawn(self._conn.send,
                                {'type': 'stop',
                                 'payload': {'id': component_id}})

    def revive(self, component_id, value):
        self._async_group.spawn(self._conn.send,
                                {'type': 'revive',
                                 'payload': {'id': component_id,
                                             'value': value}})


def run_orchestrator_subprocess(conf, conf_folder_path):
    conf_path = conf_folder_path / "orchestrator.yaml"
    json.encode_file(conf, conf_path)
    creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP
                     if sys.platform == 'win32' else 0)
    return psutil.Popen(
        ['python', '-m', 'hat.orchestrator',
         '--conf', str(conf_path),
         '--ui-path', str(conf_folder_path)],
        creationflags=creationflags)


def stop_process(p, wait_timeout=5):
    if not p.is_running():
        return
    p.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == 'win32'
                  else signal.SIGTERM)
    try:
        p.wait(wait_timeout)
    except psutil.TimeoutExpired:
        p.kill()


def wait_until(fn, *args, timeout=5):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if fn(*args):
            return
        time.sleep(0.01)
    raise TimeoutError()


def process_is_running(process):
    return process.is_running() and process.status() != 'zombie'


def process_listens_on(process, local_port):
    return bool(util.first(process.connections(),
                           lambda i: i.status == 'LISTEN' and
                           i.laddr.port == local_port))


def count_subprocess_running(process):
    return sum(1 for i in process.children() if process_is_running(process))


async def wait_status_and_assert_process(process, change_queue, status):
    while True:
        components = await change_queue.get_until_empty()
        if components[0].status == status:
            break
    assert (count_subprocess_running(process) ==
            sum(component.status == 'RUNNING' for component in components))


@pytest.fixture
def conf(unused_tcp_port_factory):
    return {
        'type': 'orchestrator',
        'log': {'version': 1},
        'components': [],
        'ui': {'address': f'http://localhost:{unused_tcp_port_factory()}'}}


@pytest.fixture
def run_orchestrator_factory(conf, tmp_path):
    processes = []

    def run_orchestrator(components):
        process = run_orchestrator_subprocess(
            conf=dict(conf, components=components),
            conf_folder_path=tmp_path)
        processes.append(process)
        return process

    yield run_orchestrator

    for process in processes:
        stop_process(process)


@pytest.fixture
@pytest.mark.asyncio
async def run_orchestrator_ui_client_factory(conf, tmp_path):
    processes = []
    clients = []

    async def run_orchestrator_ui_client(components):
        process = run_orchestrator_subprocess(
            conf=dict(conf, components=components),
            conf_folder_path=tmp_path)
        processes.append(process)
        ui_url = urllib.parse.urlparse(conf['ui']['address'])
        wait_until(process_listens_on, process, ui_url.port)
        client = await create_client(conf['ui']['address'])
        clients.append(client)
        change_queue = aio.Queue()
        client.register_components_change_cb(
            lambda: change_queue.put_nowait(client.components))
        return process, client, change_queue

    yield run_orchestrator_ui_client

    for process in processes:
        stop_process(process)
    for client in clients:
        await client.closed


def test_orchestrator_kills_children(run_orchestrator_factory):
    process = run_orchestrator_factory(
        components=[{'name': f'comp-{i}',
                     'args': ['sleep', '10'],
                     'delay': 0,
                     'revive': False} for i in range(3)])
    wait_until(lambda p: count_subprocess_running(p) == 3, process)
    children = process.children()
    stop_process(process)
    wait_until(lambda children: all(not c.is_running() for c in children),
               children)


@pytest.mark.skipif(sys.platform != 'linux', reason="not suppoprted")
def test_orchestrator_kills_children_on_kill(run_orchestrator_factory):
    process = run_orchestrator_factory(
        components=[{'name': f'comp-{i}',
                     'args': ['sleep', '10'],
                     'delay': 0,
                     'revive': False} for i in range(3)])
    wait_until(lambda p: count_subprocess_running(p) == 3, process)
    children = process.children()
    process.kill()
    wait_until(lambda children: all(not c.is_running() for c in children),
               children)


def test_revive_killed_child(run_orchestrator_factory):
    process = run_orchestrator_factory(components=[{'name': 'revive',
                                                    'args': ['sleep', '10'],
                                                    'delay': 0,
                                                    'revive': True}])
    wait_until(lambda p: count_subprocess_running(p) == 1, process)
    for child in list(process.children()):
        stop_process(child)
    wait_until(lambda p: count_subprocess_running(p) == 1, process)


def test_revive(run_orchestrator_factory):
    process = run_orchestrator_factory(components=[{'name': 'revive',
                                                    'args': ['sleep', '0.5'],
                                                    'delay': 0,
                                                    'revive': True},
                                                   {'name': 'no revive',
                                                    'args': ['sleep', '0.5'],
                                                    'delay': 0,
                                                    'revive': False}])
    wait_until(lambda p: count_subprocess_running(p) == 2, process)
    time.sleep(1.1)
    assert count_subprocess_running(process) == 1


def test_delay(run_orchestrator_factory):
    process = run_orchestrator_factory(components=[{'name': 'revive',
                                                    'args': ['sleep', '10'],
                                                    'delay': 1,
                                                    'revive': False}])
    time.sleep(0.9)
    assert count_subprocess_running(process) == 0
    wait_until(lambda p: count_subprocess_running(p) == 1, process)


# TODO: undeterministic and long execution time for win32
@pytest.mark.asyncio
async def test_process_ui_consistency(run_orchestrator_ui_client_factory):
    process, client, _ = await run_orchestrator_ui_client_factory(
        components=[{'name': 'revive',
                     'args': ['sleep', '20'],
                     'delay': 0,
                     'revive': False}])
    for _ in range(3):
        wait_until(count_subprocess_running, process)
        await asyncio.sleep(ui_timeout)
        assert client.components[0].status == 'RUNNING'
        client.stop(client.components[0].id)
        await asyncio.sleep(ui_timeout)
        assert client.components[0].status == 'STOPPED'
        assert count_subprocess_running(process) == 0
        client.start(client.components[0].id)
        await asyncio.sleep(ui_timeout)


@pytest.mark.asyncio
async def test_ui_process_consistency(run_orchestrator_ui_client_factory):
    process, client, change_queue = await run_orchestrator_ui_client_factory(
        components=[{'name': 'revive',
                     'args': ['sleep', '20'],
                     'delay': 0,
                     'revive': False}])
    for _ in range(3):
        await wait_status_and_assert_process(process, change_queue, 'RUNNING')
        client.stop(client.components[0].id)
        await wait_status_and_assert_process(process, change_queue, 'STOPPED')
        client.start(client.components[0].id)
    await wait_status_and_assert_process(process, change_queue, 'RUNNING')
    await asyncio.sleep(no_change_delay)
    assert count_subprocess_running(process) == 1
    assert change_queue.empty()


@pytest.mark.asyncio
async def test_revive_after_end(run_orchestrator_ui_client_factory):
    process, client, change_queue = await run_orchestrator_ui_client_factory(
        components=[{'name': 'revive',
                     'args': ['sleep', '0.5'],
                     'delay': 0,
                     'revive': True}])
    for i in range(3):
        await wait_status_and_assert_process(process, change_queue, 'RUNNING')
        await wait_status_and_assert_process(process, change_queue, 'STOPPED')


@pytest.mark.asyncio
async def test_revive_after_stop(run_orchestrator_ui_client_factory):
    process, client, change_queue = await run_orchestrator_ui_client_factory(
        components=[{'name': 'revive',
                     'args': ['sleep', '10'],
                     'delay': 0,
                     'revive': True}])
    for i in range(3):
        await wait_status_and_assert_process(process, change_queue, 'RUNNING')
        client.stop(client.components[0].id)
        await wait_status_and_assert_process(process, change_queue, 'STOPPED')


@pytest.mark.asyncio
async def test_revive_on_delay(run_orchestrator_ui_client_factory):
    process, client, change_queue = await run_orchestrator_ui_client_factory(
        components=[{'name': 'revive',
                     'args': ['sleep', '10'],
                     'delay': 10,
                     'revive': False}])
    await wait_status_and_assert_process(process, change_queue, 'DELAYED')
    client.revive(client.components[0].id, True)
    await wait_status_and_assert_process(process, change_queue, 'DELAYED')
    assert client.components[0].revive
    assert change_queue.empty()


@pytest.mark.asyncio
async def test_start_on_delay(run_orchestrator_ui_client_factory):
    process, client, change_queue = await run_orchestrator_ui_client_factory(
        components=[{'name': 'revive',
                     'args': ['sleep', '10'],
                     'delay': 10,
                     'revive': False}])
    await wait_status_and_assert_process(process, change_queue, 'DELAYED')
    client.start(client.components[0].id)
    await wait_status_and_assert_process(process, change_queue, 'RUNNING')


@pytest.mark.asyncio
async def test_stop_on_delay(run_orchestrator_ui_client_factory):
    process, client, change_queue = await run_orchestrator_ui_client_factory(
        components=[{'name': 'revive',
                     'args': ['sleep', '10'],
                     'delay': 10,
                     'revive': False}])
    await wait_status_and_assert_process(process, change_queue, 'DELAYED')
    client.stop(client.components[0].id)
    await wait_status_and_assert_process(process, change_queue, 'STOPPED')


@pytest.mark.asyncio
async def test_noop_revive(run_orchestrator_ui_client_factory):
    process, client, change_queue = await run_orchestrator_ui_client_factory(
        components=[{'name': 'revive',
                     'args': ['sleep', '10'],
                     'delay': 0,
                     'revive': True}])
    await wait_status_and_assert_process(process, change_queue, 'RUNNING')
    for _ in range(3):
        client.revive(client.components[0].id, True)
    await asyncio.sleep(no_change_delay)
    assert count_subprocess_running(process) == 1
    assert change_queue.empty()


@pytest.mark.asyncio
async def test_noop_start(run_orchestrator_ui_client_factory):
    process, client, change_queue = await run_orchestrator_ui_client_factory(
        components=[{'name': 'revive',
                     'args': ['sleep', '10'],
                     'delay': 0,
                     'revive': True}])
    await wait_status_and_assert_process(process, change_queue, 'RUNNING')
    for _ in range(3):
        client.start(client.components[0].id)
    await asyncio.sleep(no_change_delay)
    assert count_subprocess_running(process) == 1
    assert change_queue.empty()


@pytest.mark.asyncio
async def test_noop_stop(run_orchestrator_ui_client_factory):
    process, client, change_queue = await run_orchestrator_ui_client_factory(
        components=[{'name': 'revive',
                     'args': ['sleep', '10'],
                     'delay': 0,
                     'revive': False}])
    await wait_status_and_assert_process(process, change_queue, 'RUNNING')
    client.stop(client.components[0].id)
    await wait_status_and_assert_process(process, change_queue, 'STOPPED')
    for _ in range(3):
        client.stop(client.components[0].id)
    await asyncio.sleep(no_change_delay)
    assert count_subprocess_running(process) == 0
    assert change_queue.empty()
