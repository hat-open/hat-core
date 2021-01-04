import subprocess
import sys
import psutil
import signal
import typing

from hat import aio
from hat import json
from hat import util
import hat.juggler
import hat.monitor.client


class ServerInfo(typing.NamedTuple):
    process: psutil.Process
    monitor_port: str
    master_port: str
    ui_port: str
    parents_ports: typing.List[str]
    default_algorithm: str
    group_algorithms: typing.Dict[str, typing.List[str]]
    default_rank: int


class Cluster(typing.NamedTuple):
    server_info: ServerInfo
    components: typing.Dict[str, typing.Dict[str, 'MockComponent']]
    ui_client: 'MockUIClient'


def create_monitor_conf(monitor_port, default_rank, master_port,
                        parents_ports, default_algorithm, group_algorithms,
                        ui_port):
    return {
        'type': 'monitor',
        'log': {'version': 1},
        'server': {
            'address': f'tcp+sbs://0.0.0.0:{monitor_port}',
            'default_rank': default_rank},
        'master': {
            'address': f'tcp+sbs://0.0.0.0:{master_port}',
            'parents': [f'tcp+sbs://127.0.0.1:{parent_port}'
                        for parent_port in parents_ports],
            'default_algorithm': default_algorithm,
            'group_algorithms': group_algorithms},
        'ui': {'address': f'tcp+sbs://0.0.0.0:{ui_port}'}}


def run_monitor_subprocess(conf, conf_folder_path):
    conf_path = conf_folder_path / 'monitor.yaml'
    json.encode_file(conf, conf_path)
    creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP
                     if sys.platform == 'win32' else 0)
    return psutil.Popen(
        ['python', '-m', 'hat.monitor.server.main', '--conf', str(conf_path),
         '--ui-path', ''],
        creationflags=creationflags)


def process_is_running(process):
    return process.is_running() and process.status() != 'zombie'


def stop_process(process):
    if not process.is_running():
        return
    process.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == 'win32'
                        else signal.SIGTERM)
    try:
        process.wait(5)
    except psutil.TimeoutExpired:
        process.kill()


async def create_component_client(name, group, monitor_port,
                                  component_address):
    component = MockComponent()

    component._conf = {
        'name': name,
        'group': group,
        'monitor_address': f'tcp+sbs://127.0.0.1:{monitor_port}',
        'component_address': component_address}
    component._queue = aio.Queue()

    component._client = await hat.monitor.client.connect(component._conf)
    component._client.register_change_cb(component._state_change_cb)

    return component


class MockComponent:
    @property
    def client(self):
        return self._client

    async def next_state(self):
        return await self._queue.get()

    async def newest_state(self):
        return await self._queue.get_until_empty()

    def _state_change_cb(self):
        self._queue.put_nowait((self._client.info, self._client.components))

    async def async_close(self):
        self._queue.close()
        await self._client.async_close()


async def create_ui_client(address):
    client = MockUIClient()

    client._connection = await hat.juggler.connect(address)
    client._connection.register_change_cb(client._remote_data_change_cb)

    client._state_queue = aio.Queue()

    return client


def find_ui_info(ui_state, info):
    return util.first(ui_state['components'],
                      lambda comp: (comp['cid'] == info.cid
                                    and comp['mid'] == info.mid))


class MockUIClient:
    async def set_rank(self, component_info, rank):
        await self._connection.send({
            'type': 'set_rank',
            'payload': {
                'cid': component_info.cid,
                'mid': component_info.mid,
                'rank': rank}})

    async def get_state(self):
        return await self._state_queue.get_until_empty()

    async def async_close(self):
        await self._connection.async_close()
        self._state_queue.close()

    def _remote_data_change_cb(self):
        self._state_queue.put_nowait(self._connection.remote_data)

    def _on_exception(self, e):
        raise Exception(f'Uncaught exception in MockUIClient: {e}')
