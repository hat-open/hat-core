import subprocess
from pathlib import Path

import pytest

from hat.util import json
from hat import sbs
import hat.event.common

from test_sys.test_event.process import Process


class EventServerProcess(Process):

    def __init__(self, conf_path, local_port, ignore_stderr=False):
        super().__init__([
            'python', '-m', 'hat.event.server',
            '--conf', str(conf_path),
            '--json-schemas-path', str(json.default_schemas_json_path),
            '--sbs-schemas-path', str(sbs.default_schemas_sbs_path),
            '--additional-json-schemas-path',
            str(Path(__file__).parent / 'modules/remote.yaml')
        ], stderr=(subprocess.DEVNULL if ignore_stderr else None))
        self._local_port = local_port

    @property
    def address(self):
        return f'tcp+sbs://127.0.0.1:{self._local_port}'

    def is_active(self):
        return self.has_connection(self._local_port)

    def wait_active(self, timeout):
        self.wait_connection(self._local_port, timeout)


@pytest.fixture(scope="session")
def sbs_repo():
    return hat.event.common.create_sbs_repo()


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
def monitor_process(tmp_path, monitor_conf, monitor_port):
    conf_path = tmp_path / 'monitor.yaml'
    json.encode_file(monitor_conf, conf_path)
    args = ['python', '-m', 'hat.monitor.server',
            '--conf', str(conf_path),
            '--json-schemas-path', str(json.default_schemas_json_path),
            '--sbs-schemas-path', str(sbs.default_schemas_sbs_path),
            '--ui-path', str(tmp_path)]
    with Process(args) as p:
        p.wait_connection(monitor_port, 5)
        yield p


@pytest.fixture
def create_event_server(tmp_path, monitor_process, monitor_address,
                        unused_tcp_port_factory):
    last_server_id = 0

    def wrapper(backend_conf, modules_conf, ignore_stderr=False):
        nonlocal last_server_id
        server_id = last_server_id + 1
        last_server_id = server_id
        port = unused_tcp_port_factory()
        event_server_address = f'tcp+sbs://127.0.0.1:{port}'
        conf = {'type': 'event',
                'log': {'version': 1},
                'monitor': {'name': 'event server {server_id}',
                            'group': 'event servers',
                            'monitor_address': monitor_address,
                            'component_address': event_server_address},
                'backend_engine': {'server_id': server_id,
                                   'backend': backend_conf},
                'module_engine': {'modules': modules_conf},
                'communication': {'address': event_server_address}}

        conf_path = tmp_path / f'event_{server_id}.yaml'
        json.encode_file(conf, conf_path)

        return EventServerProcess(conf_path, port, ignore_stderr=ignore_stderr)

    return wrapper
