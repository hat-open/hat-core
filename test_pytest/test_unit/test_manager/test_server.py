import collections

import pytest

from hat import aio
from hat import json
from hat import juggler
from hat import util
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
def juggler_autoflush_sync(monkeypatch):
    monkeypatch.setattr(hat.manager.server, 'autoflush_delay', 0)


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
                            juggler_autoflush_sync):
    conf = {'settings': settings,
            'devices': []}
    srv = await hat.manager.server.create_server(conf, conf_path, ui_path)
    conn = juggler.RpcConnection(await juggler.connect(addr))

    data_settings = None

    async def wait_data_settings_change():
        nonlocal data_settings
        data_changes = aio.Queue()
        with conn.register_change_cb(lambda: data_changes.put_nowait(None)):
            while True:
                new_data_settings = json.get(conn.remote_data, 'settings')
                if new_data_settings != data_settings:
                    break
                await data_changes.get()
        data_settings = new_data_settings

    await wait_data_settings_change()
    assert data_settings == settings

    await conn.call('save')
    new_conf = json.decode_file(conf_path)
    assert new_conf['settings'] == settings

    await conn.call('set_settings', ['ui', 'address'], 'abc')

    new_settings = json.set_(settings, ['ui', 'address'], 'abc')
    await wait_data_settings_change()
    assert data_settings == new_settings

    await conn.call('save')
    new_conf = json.decode_file(conf_path)
    assert new_conf['settings'] == new_settings

    await conn.async_close()
    await srv.async_close()
