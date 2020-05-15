import pytest
import psutil
import signal
import sys
import subprocess
import time
import urllib.parse
import asyncio

from hat import util
from hat.util import json
import hat.event.client
import hat.event.common

from test_sys.test_gateway import mock_device


class Process:

    def __init__(self, cmd, ignore_stderr=False):
        creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP
                         if sys.platform == 'win32' else 0)
        self._p = psutil.Popen(
            cmd, creationflags=creationflags,
            stderr=subprocess.DEVNULL if ignore_stderr else None)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def wait_closed(self, timeout=5):
        self.close()
        if not self._p.is_running():
            return
        try:
            self._p.wait(timeout)
        except psutil.TimeoutExpired:
            self._p.kill()

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
                'parents': [],
                'default_algorithm': 'BLESS_ONE',
                'group_algorithms': {}},
            'ui': {
                'address': f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}'}}


@pytest.fixture
def event_server_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def monitor_process(tmp_path, monitor_conf, monitor_port):
    conf_path = tmp_path / 'monitor.yaml'
    json.encode_file(monitor_conf, conf_path)
    with Process(['python', '-m', 'hat.monitor.server',
                  '--conf', str(conf_path),
                  '--ui-path', str(tmp_path)]) as p:
        wait_until(p.listens_on, monitor_port)
        yield p


@pytest.fixture
def event_server_address(event_server_port):
    return f'tcp+sbs://127.0.0.1:{event_server_port}'


@pytest.fixture
def event_conf(event_server_address, monitor_address, tmp_path):
    return {'type': 'event',
            'log': {'version': 1},
            'monitor': {'name': 'es1',
                        'group': 'event_server',
                        'monitor_address': monitor_address,
                        'component_address': event_server_address},
            'backend_engine': {'server_id': 1,
                               'backend':
                                   {'module':
                                       'hat.event.server.backends.sqlite',
                                    'db_path': str(tmp_path / 'event.db'),
                                    'query_pool_size': 10}},
            'module_engine': {'modules': []},
            'communication': {'address': event_server_address}}


async def run_event_client(event_server_address, gateway_conf):
    return await hat.event.client.connect(
        event_server_address,
        subscriptions=[['gateway', gateway_conf['gateway_name'], '*']])


@pytest.fixture
@pytest.mark.asyncio
async def event_client(event_server_address, gateway_conf):
    client = await run_event_client(event_server_address, gateway_conf)

    yield client

    await client.async_close()


def run_event_server(tmp_path, event_conf):
    conf_path = tmp_path / 'event.yaml'
    json.encode_file(event_conf, conf_path)

    proc = Process(['python', '-m', 'hat.event.server',
                    '--conf', str(conf_path)])
    return proc


@pytest.fixture
def event_process(event_conf, event_server_port, tmp_path,
                  unused_tcp_port_factory):
    p = run_event_server(tmp_path, event_conf)
    assert p.is_running()
    wait_until(p.listens_on, event_server_port)

    yield p

    p.wait_closed()


@pytest.fixture()
def conf_device_factory(unused_tcp_port_factory):
    device_counter = 0

    def conf_device():
        nonlocal device_counter
        device_counter += 1
        return {'module': 'test_sys.test_gateway.mock_device',
                'name': f'mock {device_counter}',
                'address': f'http://127.0.0.1:{unused_tcp_port_factory()}'}

    return conf_device


@pytest.fixture()
def gateway_conf_no_devices(monitor_address):
    return {'type': 'gateway',
            'version': '1',
            'log': {'version': 1},
            'monitor': {'name': 'gw',
                        'group': 'gateway',
                        'monitor_address': monitor_address,
                        'component_address': None},
            'event_server_group': 'event_server',
            'gateway_name': 'gw',
            'devices': []}


@pytest.fixture(params=[1, 10])
def gateway_conf(monitor_address, gateway_conf_no_devices, conf_device_factory,
                 request):
    gateway_conf_no_devices['devices'] = [conf_device_factory()
                                          for _ in range(request.param)]
    return gateway_conf_no_devices


@pytest.fixture()
def create_gateway(tmp_path):

    def wrapper(gateway_conf, ignore_stderr=False):
        conf_path = tmp_path / 'gateway.yaml'
        json.encode_file(gateway_conf, conf_path)
        proc = Process(['python', '-m', 'hat.gateway',
                        '--conf', str(conf_path)],
                       ignore_stderr=ignore_stderr)
        wait_until(proc.is_running)
        return proc
    return wrapper


async def register_enable(event_client, conf, enable):
    for device_conf in conf['devices']:
        await event_client.register_with_response(
            [hat.event.common.RegisterEvent(
                event_type=['gateway', conf['gateway_name'],
                            mock_device.device_type, device_conf['name'],
                            'system', 'enable'],
                source_timestamp=None,
                payload=hat.event.common.EventPayload(
                    type=hat.event.common.EventPayloadType.JSON,
                    data=enable))])


async def until_devices_running(client, conf, running):
    devices = set(device_conf['name']
                  for device_conf in conf['devices'])
    while devices:
        events = await client.receive()
        for e in events:
            if e.event_type[-1] == 'running' and e.payload.data == running:
                devices.remove(e.event_type[3])


@pytest.mark.asyncio
async def test_devices_enable_disable(monitor_process, event_process,
                                      event_client, gateway_conf,
                                      create_gateway):
    device_ports = [urllib.parse.urlparse(device_conf['address']).port
                    for device_conf in gateway_conf['devices']]

    gw_process = create_gateway(gateway_conf)
    assert gw_process.is_running()

    await until_devices_running(event_client, gateway_conf, running=False)
    assert all(not gw_process.listens_on(port) for port in device_ports)

    await register_enable(event_client, gateway_conf, enable=True)
    await until_devices_running(event_client, gateway_conf, running=True)
    assert all(gw_process.listens_on(port) for port in device_ports)

    await register_enable(event_client, gateway_conf, enable=True)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(until_devices_running(
            event_client, gateway_conf, running=True), 0.1)
    assert all(gw_process.listens_on(port) for port in device_ports)

    await register_enable(event_client, gateway_conf, enable=False)
    await until_devices_running(event_client, gateway_conf, running=False)
    assert all(not gw_process.listens_on(port) for port in device_ports)

    gw_process.wait_closed()


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_devices_on_gateway_close(monitor_process, event_process,
                                        event_client, gateway_conf,
                                        create_gateway):
    device_ports = [urllib.parse.urlparse(device_conf['address']).port
                    for device_conf in gateway_conf['devices']]
    await register_enable(event_client, gateway_conf, enable=True)

    gw_process = create_gateway(gateway_conf)
    assert gw_process.is_running()

    await until_devices_running(event_client, gateway_conf, running=True)
    assert all(gw_process.listens_on(port) for port in device_ports)

    gw_process.close()

    await until_devices_running(event_client, gateway_conf, running=False)


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_device_client(monitor_process, event_process,
                             event_client, gateway_conf, create_gateway):
    await register_enable(event_client, gateway_conf, enable=True)

    gw_process = create_gateway(gateway_conf)
    assert gw_process.is_running()

    await until_devices_running(event_client, gateway_conf, running=True)
    event_types_seen_exp = []
    for device_conf in gateway_conf['devices']:
        type_payload = [
            (['gateway', gateway_conf['gateway_name'], mock_device.device_type,
             device_conf['name'], 'system', 'enable'],
             hat.event.common.EventPayload(
                 type=hat.event.common.EventPayloadType.JSON,
                 data=True)),
            (['gateway', gateway_conf['gateway_name'], mock_device.device_type,
             device_conf['name'], 'system', 'enable'], None),
            (['gateway', gateway_conf['gateway_name'], mock_device.device_type,
             device_conf['name'], 'system', 'e1'], None),
            (['gateway', gateway_conf['gateway_name'], mock_device.device_type,
             device_conf['name'], 'system', 'e2'], None),
            (['gateway', gateway_conf['gateway_name'], mock_device.device_type,
             device_conf['name'], 'e3'], None),
            (['a', 'b'], None)]
        event_types_seen_exp += [type_payload[i][0] + ['seen']
                                 for i in [2, 3]]
        event_client.register(
            [hat.event.common.RegisterEvent(
                event_type=et,
                source_timestamp=None,
                payload=payload)
             for et, payload in type_payload])

    event_types_seen = []
    while sorted(event_types_seen) != sorted(event_types_seen_exp):
        events = await event_client.receive()
        event_types_seen += [e.event_type for e in events
                             if e.event_type[-1] == 'seen']

    gw_process.close()


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_on_monitor_close(monitor_process, monitor_port,
                                gateway_conf_no_devices, create_gateway):
    gw_process = create_gateway(gateway_conf_no_devices, ignore_stderr=True)

    monitor_process.close()

    gw_process.wait_until_closed()
    assert not gw_process.is_running()

    gw_process = create_gateway(gateway_conf_no_devices, ignore_stderr=True)
    gw_process.wait_until_closed()
    assert not gw_process.is_running()


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_on_event_close(monitor_process, event_process, event_client,
                              gateway_conf, create_gateway,
                              tmp_path, event_conf, event_server_port,
                              event_server_address, monitor_port):
    device_ports = [urllib.parse.urlparse(device_conf['address']).port
                    for device_conf in gateway_conf['devices']]
    gw_process = create_gateway(gateway_conf)
    assert gw_process.is_running()
    wait_until(gw_process.connected_to, event_server_port)

    await register_enable(event_client, gateway_conf, enable=True)
    await until_devices_running(event_client, gateway_conf, running=True)

    event_process.wait_closed()
    assert gw_process.is_running()
    assert all(not gw_process.listens_on(port) for port in device_ports)

    event_proc = run_event_server(tmp_path, event_conf)
    wait_until(event_proc.listens_on, event_server_port)
    assert monitor_process.is_running()

    event_client = await run_event_client(event_server_address, gateway_conf)
    await until_devices_running(event_client, gateway_conf, running=True)

    gw_process.wait_closed()
    await event_client.async_close()
    event_proc.wait_closed()
