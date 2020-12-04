import pytest
import aiohttp
import asyncio
import contextlib
import urllib

from hat import aio
from hat import json
from hat import juggler
from hat import util
import hat.orchestrator.component
import hat.orchestrator.ui


Component = util.namedtuple(
    'Component',
    ['id', 'int'],
    ['name', 'str'],
    ['delay', 'float'],
    ['revive', 'bool'],
    ['status', 'str'])


status_ui_delay = 0.1


async def create_client(address):
    ui_address = urllib.parse.urlparse(address)
    ws_address = 'ws://{}:{}/ws'.format(ui_address.hostname,
                                        ui_address.port)
    client = Client()
    client._conn = await juggler.connect(ws_address,
                                         autoflush_delay=0)
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
        await self._conn.async_close()

    async def start(self, component_id):
        await self._conn.send({'type': 'start',
                               'payload': {
                                   'id': component_id}})

    async def stop(self, component_id):
        await self._conn.send({'type': 'stop',
                               'payload': {
                                   'id': component_id}})

    async def revive(self, component_id, value):
        await self._conn.send({'type': 'revive',
                               'payload': {
                                   'id': component_id,
                                   'value': value}})


async def create_client_with_components_queue(address):
    client = await create_client(address)
    components_queue = aio.Queue()
    client.register_components_change_cb(
        lambda: components_queue.put_nowait(client.components))
    return client, components_queue


async def create_server(address, static_dir, components):
    return await hat.orchestrator.ui.create(
        {'address': address}, static_dir, components)


async def wait_for_status(components_queue, status):
    component_status = None
    while not component_status == status:
        components = await components_queue.get_until_empty()
        component_status = components[0].status


@pytest.fixture
def short_start_delay(monkeypatch):
    monkeypatch.setattr(hat.orchestrator.component, 'start_delay', 0.01)


@pytest.fixture
def server_address(unused_tcp_port_factory):
    port = unused_tcp_port_factory()
    return f'http://localhost:{port}'


@pytest.fixture
def short_autoflush_delay(monkeypatch):
    monkeypatch.setattr(hat.orchestrator.ui, 'autoflush_delay', 0)


@pytest.mark.asyncio
async def test_backend_to_frontend(short_start_delay, server_address, tmpdir,
                                   short_autoflush_delay):
    conf = {'name': 'comp-xy',
            'args': ['sleep', '0.01'],
            'delay': 0.1,
            'revive': False}

    component = hat.orchestrator.component.Component(conf)
    server = await create_server(server_address, tmpdir, [component])
    client, components_queue = await create_client_with_components_queue(
        server_address)

    assert client.components == []

    components = await components_queue.get()
    assert components[0].name == conf['name']
    assert components[0].delay == conf['delay']
    assert components[0].revive == conf['revive']
    assert components[0].status == 'DELAYED'

    components = await components_queue.get()
    assert components[0].status == 'STARTING'

    components = await components_queue.get()
    assert components[0].status == 'RUNNING'

    await asyncio.wait_for(wait_for_status(components_queue, 'STOPPED'),
                           status_ui_delay)

    assert components_queue.empty()

    await component.async_close()
    await client.async_close()
    await server.async_close()
    assert server.closed.done()


@pytest.mark.asyncio
async def test_frontend_to_backend(short_start_delay, server_address, tmpdir,
                                   short_autoflush_delay):
    conf = {'name': 'comp-xy',
            'args': ['sleep', '50'],
            'delay': 0.1,
            'revive': False}
    component = hat.orchestrator.component.Component(conf)
    server = await create_server(server_address, tmpdir, [component])
    client, components_queue = await create_client_with_components_queue(
        server_address)

    components = await components_queue.get()
    component_id = components[0].id

    assert components[0].status == 'DELAYED'
    components = await components_queue.get()
    assert components[0].status == 'STARTING'

    components = await components_queue.get()
    assert components[0].status == 'RUNNING'

    await client.stop(component_id)
    await client.start(component_id)
    await client.stop(component_id)
    await client.start(component_id)
    await client.stop(component_id)

    await asyncio.wait_for(wait_for_status(components_queue, 'STOPPED'),
                           status_ui_delay)

    await client.revive(component_id, True)
    components = await components_queue.get()
    assert components[0].revive
    components = await components_queue.get()
    assert components[0].status == 'STARTING'
    components = await components_queue.get()
    assert components[0].status == 'RUNNING'

    assert components_queue.empty()

    await component.async_close()
    await server.async_close()
    assert server.closed.done()
    await client.closed


@pytest.mark.asyncio
async def test_get_static_files(server_address, tmpdir):
    with open(tmpdir / 'index.html', 'w', encoding='utf-8') as f:
        f.write('123')
    server = await create_server(server_address, tmpdir, [])

    async with aiohttp.ClientSession() as session:
        async with session.get(server_address + '/index.html') as resp:
            assert resp.status == 200
            assert '123' == (await resp.text())

    async with aiohttp.ClientSession() as session:
        async with session.get(server_address) as resp:
            assert resp.status == 200
            assert '123' == (await resp.text())

    async with aiohttp.ClientSession() as session:
        async with session.get(server_address + '/abc.txt') as resp:
            assert resp.status == 404

    await server.async_close()


@pytest.mark.asyncio
async def test_connect_disconnect(server_address, tmpdir):
    server = await create_server(server_address, tmpdir, [])
    assert not server.closed.done()

    client = await create_client(server_address)
    assert not client.closed.done()

    await client.async_close()
    assert client.closed.done()
    assert not server.closed.done()

    await asyncio.sleep(0.001)

    await server.async_close()
    assert server.closed.done()


@pytest.mark.timeout(1)
@pytest.mark.asyncio
async def test_invalid_client_message(server_address, tmpdir):
    server = await create_server(server_address, tmpdir, [])

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(server_address + '/ws') as ws:
            await ws.send_bytes(b'123')
            while not ws.closed:
                await ws.receive()

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(server_address + '/ws') as ws:
            await ws.send_str(json.encode({'type': 'invalid'}))
            while not ws.closed:
                await ws.receive()

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(server_address + '/ws') as ws:
            await ws.send_str(json.encode({'type': 'start', 'id': 'invalid'}))
            while not ws.closed:
                await ws.receive()

    await server.async_close()


@pytest.mark.asyncio
@pytest.mark.parametrize("responsive", [True, False])
async def test_close_server_with_active_websocket(server_address, tmpdir,
                                                  responsive):

    async def wait_ws_closed(ws):
        with contextlib.suppress(BaseException):
            while not ws.closed:
                if responsive:
                    await ws.receive()
                else:
                    await asyncio.sleep(0.001)

    server = await create_server(server_address, tmpdir, [])
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(server_address + '/ws') as ws:
            closed_future = asyncio.ensure_future(wait_ws_closed(ws))
            await server.async_close()
            closed_future.cancel()
            await closed_future

    await asyncio.sleep(0.001)
