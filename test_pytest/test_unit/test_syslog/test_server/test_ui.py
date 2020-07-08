import pytest
import urllib.parse
import datetime
import asyncio
import aiohttp

from hat import juggler
from hat import util
from hat.util import aio
import hat.syslog.server.conf
import hat.syslog.server.backend
import hat.syslog.server.ui
import hat.syslog.server.common


def ts_now():
    return datetime.datetime.now(tz=datetime.timezone.utc).timestamp()


def assert_client_vs_server_state(client):
    assert client.server_state['filter'] == client.state._replace(
        max_results=hat.syslog.server.ui.max_results_limit)


async def create_client(conf_ui):
    client = Client()
    ui_port = urllib.parse.urlparse(conf_ui.addr).port
    client._conn = await juggler.connect(f'ws://127.0.0.1:{ui_port}/ws')
    client._conn.set_local_data(hat.syslog.server.common.Filter()._asdict())
    return client


class Client:

    @property
    def closed(self):
        return self._conn.closed

    async def async_close(self):
        await self._conn.async_close()

    @property
    def state(self):
        return hat.syslog.server.common.Filter(**self._conn.local_data)

    @property
    def server_state(self):
        if not self._conn.remote_data:
            return
        return {
            'filter': (hat.syslog.server.common.Filter(
                **self._conn.remote_data['filter'])
                       if self._conn.remote_data['filter'] else None),
            'entries': [hat.syslog.server.common.entry_from_json(e)
                        for e in self._conn.remote_data['entries']],
            'first_id': self._conn.remote_data['first_id'],
            'last_id': self._conn.remote_data['last_id']}

    def register_change_cb(self, cb):
        return self._conn.register_change_cb(cb)

    def set_filter(self, filter):
        self._conn.set_local_data(
            hat.syslog.server.common.filter_to_json(filter))


@pytest.fixture
def short_register_delay(monkeypatch):
    monkeypatch.setattr(hat.syslog.server.backend, "register_delay", 0.0)


@pytest.fixture
def short_sync_local_delay(monkeypatch):
    monkeypatch.setattr(juggler, "sync_local_delay", 0.0)


@pytest.fixture
def small_max_results(monkeypatch):
    monkeypatch.setattr(hat.syslog.server.ui, "max_results_limit", 20)


@pytest.fixture
def conf_ui(tmp_path, unused_tcp_port_factory):
    # TODO: test pem file and https
    ui_path = tmp_path / 'ui'
    ui_path.mkdir()
    return hat.syslog.server.conf.WebServerConf(
        path=ui_path,
        addr=f'http://0.0.0.0:{unused_tcp_port_factory()}')


@pytest.fixture
def conf_db(tmp_path):
    path_db = tmp_path / 'syslog.db'
    return hat.syslog.server.conf.BackendConf(
        path=path_db,
        low_size=50,
        high_size=100,
        enable_archive=True)


@pytest.fixture
@pytest.mark.asyncio
async def backend_ui(conf_ui, conf_db, short_register_delay):
    backend = await hat.syslog.server.backend.create_backend(conf_db)
    web_server = await hat.syslog.server.ui.create_web_server(
        conf_ui, backend)

    yield backend, web_server

    await backend.async_close()
    await web_server.async_close()
    assert web_server.closed.done()


@pytest.fixture
@pytest.mark.asyncio
async def client(conf_ui, short_sync_local_delay):
    client = await create_client(conf_ui)

    yield client

    await client.async_close()


@pytest.fixture
def message_factory():
    counter = 0
    severities = ['DEBUG', 'INFORMATIONAL', 'WARNING', 'ERROR', 'CRITICAL']

    def f():
        nonlocal counter
        counter += 1
        ts = ts_now()
        return hat.syslog.server.common.Msg(
            facility=hat.syslog.server.common.Facility.USER,
            severity=hat.syslog.server.common.Severity[
                severities[counter % len(severities)]],
            version=1,
            timestamp=ts,
            hostname=None,
            app_name=None,
            procid=None,
            msgid='test_syslog.web',
            data="",
            msg=f'message no {counter}')

    return f


@pytest.mark.asyncio
async def test_backend_to_frontend(backend_ui, client, message_factory):
    client_change_queue = aio.Queue()
    client.register_change_cb(lambda: client_change_queue.put_nowait(None))
    backend, ui = backend_ui
    entry_queue = aio.Queue()
    backend.register_change_cb(lambda e: entry_queue.put_nowait(e))

    await client_change_queue.get()
    assert_client_vs_server_state(client)

    entries = []
    for _ in range(10):
        msg = message_factory()
        await backend.register(ts_now(), msg)
        reg_entries = await entry_queue.get()
        entry = reg_entries[0]
        entries.insert(0, entry)
        await client_change_queue.get()
        assert entry in client.server_state['entries']
        assert util.first(client.server_state['entries'],
                          lambda i: i.msg == msg)
    assert entries == client.server_state['entries']
    assert client.server_state['first_id'] == 1
    assert client.server_state['last_id'] == len(entries)
    assert_client_vs_server_state(client)


@pytest.mark.asyncio
async def test_backend_to_frontend_timeout(backend_ui, client,
                                           message_factory):
    client_change_queue = aio.Queue()
    client.register_change_cb(lambda: client_change_queue.put_nowait(None))
    await client_change_queue.get()

    backend, ui = backend_ui
    async with aio.Group() as group:
        for _ in range(50):
            group.spawn(backend.register, ts_now(), message_factory())
    await asyncio.wait_for(client_change_queue.get(), 0.1)
    assert len(client.server_state['entries']) == 50


@pytest.mark.asyncio
async def test_frontend_to_backend(backend_ui, client, message_factory):
    backend, ui = backend_ui
    client_change_queue = aio.Queue()
    client.register_change_cb(lambda: client_change_queue.put_nowait(None))
    client.set_filter(hat.syslog.server.common.Filter(msg='message no 1'))

    await client_change_queue.get()
    await client_change_queue.get()
    assert_client_vs_server_state(client)

    for _ in range(10):
        await backend.register(ts_now(), message_factory())
        await client_change_queue.get()

    assert len(client.server_state['entries']) == 2
    assert all('message no 1' in e.msg.msg
               for e in client.server_state['entries'])

    client.set_filter(hat.syslog.server.common.Filter())
    await client_change_queue.get()
    assert len(client.server_state['entries']) == 10
    assert client_change_queue.empty()

    client.set_filter(hat.syslog.server.common.Filter(msg='bla bla'))
    await client_change_queue.get()
    assert len(client.server_state['entries']) == 0
    assert client_change_queue.empty()

    client.set_filter(hat.syslog.server.common.Filter(
        severity=hat.syslog.server.common.Severity.ERROR))
    await client_change_queue.get()
    assert len(client.server_state['entries']) == 2
    assert all(e.msg.severity == hat.syslog.server.common.Severity.ERROR
               for e in client.server_state['entries'])


@pytest.mark.asyncio
async def test_max_size(backend_ui, client, message_factory,
                        small_max_results):
    backend, ui = backend_ui
    client_change_queue = aio.Queue()
    client.register_change_cb(lambda: client_change_queue.put_nowait(None))

    await client_change_queue.get()
    await client_change_queue.get()
    assert_client_vs_server_state(client)

    for _ in range(40):
        await backend.register(ts_now(), message_factory())
        await client_change_queue.get()

    assert len(client.server_state['entries']) == 20
    entry_ids_exp = list(reversed(range(21, 41)))
    assert [e.id for e in client.server_state['entries']] == entry_ids_exp

    client.set_filter(hat.syslog.server.common.Filter(max_results=35))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client_change_queue.get(), 0.1)
    assert_client_vs_server_state(client)
    assert len(client.server_state['entries']) == 20
    assert [e.id for e in client.server_state['entries']] == entry_ids_exp


@pytest.mark.asyncio
async def test_get_static_files(backend_ui, conf_ui):
    with open(conf_ui.path / 'index.html', 'w', encoding='utf-8') as f:
        f.write('123')

    async with aiohttp.ClientSession() as session:
        async with session.get(conf_ui.addr + '/index.html') as resp:
            assert resp.status == 200
            assert '123' == (await resp.text())

    async with aiohttp.ClientSession() as session:
        async with session.get(conf_ui.addr) as resp:
            assert resp.status == 200
            assert '123' == (await resp.text())

    async with aiohttp.ClientSession() as session:
        async with session.get(conf_ui.addr + '/abc.txt') as resp:
            assert resp.status == 404


@pytest.mark.parametrize("client_cont", [1])
@pytest.mark.asyncio
async def test_connect_disconnect(backend_ui, conf_ui, message_factory,
                                  short_sync_local_delay, client_cont):
    backend, ui = backend_ui
    message_count = 3
    async with aio.Group() as group:
        for _ in range(message_count):
            group.spawn(backend.register, ts_now(), message_factory())

    clients = set()
    for _ in range(client_cont):
        client = await create_client(conf_ui)
        client_change_queue = aio.Queue()
        client.register_change_cb(lambda: client_change_queue.put_nowait(None))
        assert not client.closed.done()
        await client_change_queue.get()
        await asyncio.sleep(0.1)
        assert len(client.server_state['entries']) == message_count
        clients.add(client)

    while clients:
        client = clients.pop()
        await client.async_close()
        assert client.closed.done()

    await asyncio.sleep(0.001)

    assert not backend.closed.done()
    assert not ui.closed.done()
