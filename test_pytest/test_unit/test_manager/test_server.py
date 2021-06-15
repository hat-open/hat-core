import collections

import pytest

from hat import aio
from hat import json
from hat import juggler
from hat import util
from hat.manager import common
import hat.manager.devices
import hat.manager.server


pytestmark = pytest.mark.asyncio


@pytest.fixture
def port():
    return util.get_unused_tcp_port()


@pytest.fixture
def addr(port):
    return f'ws://127.0.0.1:{port}/ws'


@pytest.fixture
def settings(port):
    return {'ui': {'address': f'http://127.0.0.1:{port}'},
            'log': {'level': 'DEBUG',
                    'syslog': {'enabled': False,
                               'host': '127.0.0.1',
                               'port': 6514},
                    'console': {'enabled': False}}}


@pytest.fixture
def conf_path(tmp_path):
    return tmp_path / 'manager.json'


@pytest.fixture
def ui_path(tmp_path):
    return tmp_path


@pytest.fixture
def patch_autoflush(monkeypatch):
    monkeypatch.setattr(hat.manager.server, 'autoflush_delay', 0)


@pytest.fixture
def patch_autostart(monkeypatch):
    monkeypatch.setattr(hat.manager.server, 'autostart_delay', 0.1)


@pytest.fixture
def patch_device_queue(monkeypatch):
    queue = aio.Queue()

    def get_default_conf(device_type):
        return {}

    def create_device(conf, logger):
        device = Device(conf, logger)
        queue.put_nowait(device)
        return device

    monkeypatch.setattr(hat.manager.devices, 'get_default_conf',
                        get_default_conf)
    monkeypatch.setattr(hat.manager.devices, 'create_device',
                        create_device)
    return queue


def create_remote_data_change_queue(conn, path):
    queue = aio.Queue()
    last_data = None

    def on_change():
        nonlocal last_data
        new_data = json.get(conn.remote_data, path)
        if new_data == last_data:
            return
        queue.put_nowait(new_data)
        last_data = new_data

    conn.register_change_cb(on_change)
    return queue


class Resource(aio.Resource):

    def __init__(self):
        self._async_group = aio.Group()

    @property
    def async_group(self):
        return self._async_group


class Device(common.Device):

    def __init__(self, conf, logger):
        self._conf = conf
        self._logger = logger
        self._data = common.DataStorage()

    @property
    def conf(self):
        return self._conf

    @property
    def logger(self):
        return self._logger

    @property
    def data(self):
        return self._data

    def get_conf(self):
        return self._conf

    async def create(self):
        return Resource()

    async def execute(self, action, *args):
        return {'action': action,
                'args': list(args)}


async def test_create(settings, conf_path, ui_path):
    conf = {'settings': settings,
            'devices': []}

    srv = await hat.manager.server.create_server(conf, conf_path, ui_path)

    assert srv.is_open

    await srv.async_close()

    assert srv.is_closed


@pytest.mark.parametrize("conn_count", [1, 2, 5])
async def test_connect(settings, conf_path, ui_path, addr, conn_count):
    conf = {'settings': settings,
            'devices': []}
    srv = await hat.manager.server.create_server(conf, conf_path, ui_path)

    conns = collections.deque()
    for _ in range(conn_count):
        conn = await juggler.connect(addr)
        conns.append(conn)

    while conns:
        for conn in conns:
            assert conn.is_open

        conn = conns.pop()
        await conn.async_close()

    assert srv.is_open

    await srv.async_close()


async def test_save(settings, conf_path, ui_path, addr):
    conf = {'settings': settings,
            'devices': []}
    srv = await hat.manager.server.create_server(conf, conf_path, ui_path)
    conn = juggler.RpcConnection(await juggler.connect(addr))

    assert conf_path.exists() is False

    await conn.call('save')

    assert conf_path.exists() is True

    new_conf = json.decode_file(conf_path)

    assert new_conf['settings'] == conf['settings']
    assert new_conf['devices'] == conf['devices']

    await conn.async_close()
    await srv.async_close()


async def test_set_settings(settings, conf_path, ui_path, addr,
                            patch_autoflush):
    conf = {'settings': settings,
            'devices': []}
    srv = await hat.manager.server.create_server(conf, conf_path, ui_path)
    conn = juggler.RpcConnection(await juggler.connect(addr))
    data_settings_queue = create_remote_data_change_queue(conn, 'settings')

    data_settings = await data_settings_queue.get()
    assert data_settings == settings

    await conn.call('save')
    new_conf = json.decode_file(conf_path)
    assert new_conf['settings'] == settings

    await conn.call('set_settings', ['ui', 'address'], 'abc')
    new_settings = json.set_(settings, ['ui', 'address'], 'abc')
    data_settings = await data_settings_queue.get()
    assert data_settings == new_settings

    await conn.call('save')
    new_conf = json.decode_file(conf_path)
    assert new_conf['settings'] == new_settings

    await conn.async_close()
    await srv.async_close()


@pytest.mark.parametrize("device_count", [1, 2, 5])
async def test_init_device(settings, conf_path, ui_path, addr,
                           patch_autoflush, patch_device_queue, device_count):
    conf = {'settings': settings,
            'devices': [{'type': f'type{i}',
                         'name': f'name{i}',
                         'autostart': False}
                        for i in range(device_count)]}

    srv = await hat.manager.server.create_server(conf, conf_path, ui_path)

    device_type_names = set()
    for _ in range(device_count):
        device = await patch_device_queue.get()
        device_type_names.add((device.conf['type'], device.conf['name']))

    assert device_type_names == {(i['type'], i['name'])
                                 for i in conf['devices']}

    await srv.async_close()


async def test_add_remove_device(settings, conf_path, ui_path, addr,
                                 patch_autoflush, patch_device_queue):
    conf = {'settings': settings,
            'devices': []}
    srv = await hat.manager.server.create_server(conf, conf_path, ui_path)
    conn = juggler.RpcConnection(await juggler.connect(addr))
    data_devices_queue = create_remote_data_change_queue(conn, 'devices')

    data_devices = await data_devices_queue.get()
    assert data_devices == {}

    device_id = await conn.call('add', 'device_type')
    data_devices = await data_devices_queue.get()
    assert device_id in data_devices
    assert data_devices[device_id]['type'] == 'device_type'

    await conn.call('set_name', device_id, 'abc')
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['name'] == 'abc'

    await conn.call('save')
    new_conf = json.decode_file(conf_path)
    assert len(new_conf['devices']) == 1
    assert new_conf['devices'][0]['type'] == 'device_type'
    assert new_conf['devices'][0]['name'] == 'abc'

    await conn.call('remove', device_id)
    data_devices = await data_devices_queue.get()
    assert data_devices == {}

    await conn.async_close()
    await srv.async_close()


async def test_start_stop_device(settings, conf_path, ui_path, addr,
                                 patch_autoflush, patch_device_queue):
    conf = {'settings': settings,
            'devices': []}
    srv = await hat.manager.server.create_server(conf, conf_path, ui_path)
    conn = juggler.RpcConnection(await juggler.connect(addr))
    data_devices_queue = create_remote_data_change_queue(conn, 'devices')

    data_devices = await data_devices_queue.get()
    assert data_devices == {}

    device_id = await conn.call('add', 'device_type')
    data_devices = await data_devices_queue.get()
    assert device_id in data_devices
    assert data_devices[device_id]['status'] == 'stopped'

    await conn.call('start', device_id)
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'starting'
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'started'

    await conn.call('stop', device_id)
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'stopping'
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'stopped'

    await conn.async_close()
    await srv.async_close()


async def test_execute(settings, conf_path, ui_path, addr,
                       patch_autoflush, patch_device_queue):
    conf = {'settings': settings,
            'devices': []}
    srv = await hat.manager.server.create_server(conf, conf_path, ui_path)
    conn = juggler.RpcConnection(await juggler.connect(addr))
    device_id = await conn.call('add', 'device_type')

    result = await conn.call('execute', device_id, 'abc', 123)
    assert result == {'action': 'abc',
                      'args': [123]}

    await conn.async_close()
    await srv.async_close()


async def test_autostart(settings, conf_path, ui_path, addr,
                         patch_autoflush, patch_device_queue,
                         patch_autostart):
    conf = {'settings': settings,
            'devices': []}
    srv = await hat.manager.server.create_server(conf, conf_path, ui_path)
    conn = juggler.RpcConnection(await juggler.connect(addr))
    data_devices_queue = create_remote_data_change_queue(conn, 'devices')

    data_devices = await data_devices_queue.get()
    assert data_devices == {}

    device_id = await conn.call('add', 'device_type')
    data_devices = await data_devices_queue.get()
    assert device_id in data_devices
    assert data_devices[device_id]['status'] == 'stopped'

    await conn.call('set_autostart', device_id, True)
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['autostart'] is True

    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'starting'
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'started'

    await conn.call('stop', device_id)
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'stopping'
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'stopped'
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'starting'
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'started'

    await conn.call('set_autostart', device_id, False)
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['autostart'] is False

    await conn.call('stop', device_id)
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'stopping'
    data_devices = await data_devices_queue.get()
    assert data_devices[device_id]['status'] == 'stopped'

    await conn.async_close()
    await srv.async_close()
