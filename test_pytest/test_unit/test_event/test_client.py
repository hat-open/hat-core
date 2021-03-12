import asyncio

import pytest

from hat import aio
from hat import chatter
from hat import util
from hat.event import common
import hat.event.client
import hat.monitor.common


pytestmark = pytest.mark.asyncio


@pytest.fixture
def patch_reconnect_delay(monkeypatch):
    monkeypatch.setattr(hat.event.client, 'reconnect_delay', 0.01)


@pytest.fixture
def server_port():
    return util.get_unused_tcp_port()


@pytest.fixture
def server_address(server_port):
    return f'tcp+sbs://127.0.0.1:{server_port}'


async def create_server(address):
    server = Server()
    server._conn_queue = aio.Queue()
    server._srv = await chatter.listen(
        common.sbs_repo, address,
        lambda conn: server._conn_queue.put_nowait(Connection(conn)))
    return server


class Server(aio.Resource):

    @property
    def async_group(self):
        return self._srv.async_group

    async def get_connection(self):
        return await self._conn_queue.get()


class Connection(aio.Resource):

    def __init__(self, conn):
        self._conn = conn

    @property
    def async_group(self):
        return self._conn.async_group

    def send_notify(self, events):
        data = chatter.Data(module='HatEvent',
                            type='MsgNotify',
                            data=[common.event_to_sbs(event)
                                  for event in events])
        self._conn.send(data)

    def send_query_res(self, conv, events):
        data = chatter.Data(module='HatEvent',
                            type='MsgQueryRes',
                            data=[common.event_to_sbs(event)
                                  for event in events])
        self._conn.send(data, conv=conv)

    def send_register_res(self, conv, events):
        data = chatter.Data(module='HatEvent',
                            type='MsgRegisterRes',
                            data=[(('event', common.event_to_sbs(event))
                                   if event else ('failure', None))
                                  for event in events])
        self._conn.send(data, conv=conv)

    async def receive(self):
        return await self._conn.receive()


class MonitorClient(aio.Resource):

    def __init__(self):
        self._async_group = aio.Group()
        self._components = []
        self._change_cbs = util.CallbackRegistry()

    @property
    def async_group(self):
        return self._async_group

    @property
    def components(self):
        return self._components

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    def change(self, components):
        self._components = components
        self._change_cbs.notify()


async def test_client_connect_failure(server_address):
    with pytest.raises(ConnectionError):
        await hat.event.client.connect(server_address)


async def test_client_connect(server_address):
    server = await create_server(server_address)
    client = await hat.event.client.connect(server_address)
    conn = await server.get_connection()

    assert server.is_open
    assert client.is_open
    assert conn.is_open

    await server.async_close()
    await client.wait_closed()
    await conn.wait_closed()


async def test_client_subscriptions(server_address):
    server = await create_server(server_address)

    client = await hat.event.client.connect(server_address)
    conn = await server.get_connection()

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(conn.receive(), 0.01)

    await client.async_close()
    await conn.wait_closed()

    subscriptions = [('a',),
                     ('b', '*')]
    client = await hat.event.client.connect(server_address, subscriptions)
    conn = await server.get_connection()

    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is True
    assert msg.data == chatter.Data('HatEvent', 'MsgSubscribe',
                                    [list(i) for i in subscriptions])

    await conn.async_close()
    await client.async_close()

    await server.async_close()


async def test_client_receive(server_address):
    events = [
        common.Event(
            event_id=common.EventId(1, 2),
            event_type=('a', 'b', 'c'),
            timestamp=common.now(),
            source_timestamp=None,
            payload=common.EventPayload(common.EventPayloadType.JSON, i))
        for i in range(10)]

    server = await create_server(server_address)
    client = await hat.event.client.connect(server_address)
    conn = await server.get_connection()

    conn.send_notify([])
    received = await client.receive()
    assert received == []

    conn.send_notify(events)
    received = await client.receive()
    assert received == events

    await conn.async_close()
    await client.async_close()
    await server.async_close()

    with pytest.raises(ConnectionError):
        await client.receive()


async def test_client_register(server_address):
    register_events = [
        common.RegisterEvent(
            event_type=('a', 'b', 'c'),
            source_timestamp=common.now(),
            payload=common.EventPayload(common.EventPayloadType.JSON, i))
        for i in range(10)]

    server = await create_server(server_address)
    client = await hat.event.client.connect(server_address)
    conn = await server.get_connection()

    client.register([])
    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is True
    assert msg.data == chatter.Data('HatEvent', 'MsgRegisterReq', [])

    client.register(register_events)
    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is True
    assert msg.data == chatter.Data('HatEvent', 'MsgRegisterReq',
                                    [common.register_event_to_sbs(i)
                                     for i in register_events])

    await conn.async_close()
    await client.async_close()
    await server.async_close()

    with pytest.raises(ConnectionError):
        client.register(register_events)


async def test_client_register_with_response(server_address):
    register_events = [
        common.RegisterEvent(
            event_type=('a', 'b', 'c'),
            source_timestamp=common.now(),
            payload=common.EventPayload(common.EventPayloadType.JSON, i))
        for i in range(10)]

    events = [
        common.Event(
            event_id=common.EventId(1, 2),
            event_type=register_event.event_type,
            timestamp=common.now(),
            source_timestamp=register_event.source_timestamp,
            payload=register_event.payload)
        for register_event in register_events]

    events = [event if i % 2 else None
              for i, event in enumerate(events)]

    server = await create_server(server_address)
    client = await hat.event.client.connect(server_address)
    conn = await server.get_connection()

    register_future = asyncio.ensure_future(client.register_with_response([]))
    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is False
    assert msg.data == chatter.Data('HatEvent', 'MsgRegisterReq', [])
    assert not register_future.done()
    conn.send_register_res(msg.conv, [])
    received = await register_future
    assert received == []

    register_future = asyncio.ensure_future(
        client.register_with_response(register_events))
    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is False
    assert msg.data == chatter.Data('HatEvent', 'MsgRegisterReq',
                                    [common.register_event_to_sbs(i)
                                     for i in register_events])
    assert not register_future.done()
    conn.send_register_res(msg.conv, events)
    received = await register_future
    assert received == events

    await conn.async_close()
    await client.async_close()
    await server.async_close()

    with pytest.raises(ConnectionError):
        await client.register_with_response(register_events)


async def test_client_query(server_address):
    events = [
        common.Event(
            event_id=common.EventId(1, 2),
            event_type=('a', 'b', 'c'),
            timestamp=common.now(),
            source_timestamp=None,
            payload=common.EventPayload(common.EventPayloadType.JSON, i))
        for i in range(10)]

    server = await create_server(server_address)
    client = await hat.event.client.connect(server_address)
    conn = await server.get_connection()

    query_data = common.QueryData()
    query_future = asyncio.ensure_future(client.query(query_data))
    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is False
    assert msg.data == chatter.Data('HatEvent', 'MsgQueryReq',
                                    common.query_to_sbs(query_data))
    assert not query_future.done()
    conn.send_query_res(msg.conv, [])
    received = await query_future
    assert received == []

    query_data = common.QueryData(event_types=[['*']])
    query_future = asyncio.ensure_future(client.query(query_data))
    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is False
    assert msg.data == chatter.Data('HatEvent', 'MsgQueryReq',
                                    common.query_to_sbs(query_data))
    assert not query_future.done()
    conn.send_query_res(msg.conv, events)
    received = await query_future
    assert received == events

    await conn.async_close()
    await client.async_close()
    await server.async_close()

    with pytest.raises(ConnectionError):
        await client.query(common.QueryData())


async def test_run_client(server_address):
    component_info = hat.monitor.common.ComponentInfo(cid=1,
                                                      mid=2,
                                                      name='name',
                                                      group='group',
                                                      address=server_address,
                                                      rank=3,
                                                      blessing=None,
                                                      ready=None)

    client_queue = aio.Queue()

    async def run_cb(client):
        client_queue.put_nowait(client)
        try:
            await asyncio.Future()
        finally:
            client_queue.put_nowait(None)

    monitor_client = MonitorClient()
    server = await create_server(server_address)

    run_future = asyncio.ensure_future(
        hat.event.client.run_client(monitor_client, component_info.group,
                                    run_cb))

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client_queue.get(), 0.01)

    monitor_client.change([component_info])
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client_queue.get(), 0.01)

    monitor_client.change([component_info._replace(blessing=123, ready=123)])
    client = await client_queue.get()
    conn = await server.get_connection()

    assert client.is_open
    assert conn.is_open

    monitor_client.change([component_info])
    await client.wait_closed()
    await conn.wait_closed()
    client = await client_queue.get()
    assert client is None

    assert not run_future.done()

    await monitor_client.async_close()
    with pytest.raises(ConnectionError):
        await run_future

    await server.async_close()


async def test_run_client_return(server_address):
    component_info = hat.monitor.common.ComponentInfo(cid=1,
                                                      mid=2,
                                                      name='name',
                                                      group='group',
                                                      address=server_address,
                                                      rank=3,
                                                      blessing=None,
                                                      ready=None)

    async def run_cb(client):
        await asyncio.sleep(0)
        return 123

    monitor_client = MonitorClient()
    server = await create_server(server_address)

    run_future = asyncio.ensure_future(
        hat.event.client.run_client(monitor_client, component_info.group,
                                    run_cb))

    monitor_client.change([component_info._replace(blessing=1, ready=1)])
    conn = await server.get_connection()

    result = await run_future
    assert result == 123

    await conn.wait_closed()

    await monitor_client.async_close()
    await server.async_close()


async def test_run_client_exception(server_address):
    component_info = hat.monitor.common.ComponentInfo(cid=1,
                                                      mid=2,
                                                      name='name',
                                                      group='group',
                                                      address=server_address,
                                                      rank=3,
                                                      blessing=None,
                                                      ready=None)

    async def run_cb(client):
        await asyncio.sleep(0)
        raise Exception()

    monitor_client = MonitorClient()
    server = await create_server(server_address)

    run_future = asyncio.ensure_future(
        hat.event.client.run_client(monitor_client, component_info.group,
                                    run_cb))

    monitor_client.change([component_info._replace(blessing=1, ready=1)])
    conn = await server.get_connection()

    with pytest.raises(Exception):
        await run_future

    await conn.wait_closed()

    await monitor_client.async_close()
    await server.async_close()


async def test_run_client_reconnect(patch_reconnect_delay, server_address):
    component_info = hat.monitor.common.ComponentInfo(cid=1,
                                                      mid=2,
                                                      name='name',
                                                      group='group',
                                                      address=server_address,
                                                      rank=3,
                                                      blessing=None,
                                                      ready=None)

    client_queue = aio.Queue()

    async def run_cb(client):
        client_queue.put_nowait(client)
        try:
            await asyncio.Future()
        finally:
            client_queue.put_nowait(None)

    monitor_client = MonitorClient()
    server = await create_server(server_address)

    run_future = asyncio.ensure_future(
        hat.event.client.run_client(monitor_client, component_info.group,
                                    run_cb))

    monitor_client.change([component_info._replace(blessing=123, ready=123)])
    client = await client_queue.get()
    conn = await server.get_connection()

    monitor_client.change([component_info])
    await client.wait_closed()
    await conn.wait_closed()
    client = await client_queue.get()
    assert client is None

    monitor_client.change([component_info._replace(blessing=123, ready=123)])
    client = await client_queue.get()
    conn = await server.get_connection()

    await server.async_close()
    await conn.wait_closed()
    await client.wait_closed()
    client = await client_queue.get()
    assert client is None

    server = await create_server(server_address)
    client = await client_queue.get()
    conn = await server.get_connection()

    assert not run_future.done()

    await monitor_client.async_close()
    with pytest.raises(ConnectionError):
        await run_future
    await client.wait_closed()
    await conn.wait_closed()

    await server.async_close()


async def test_run_client_cancellation(server_address):
    component_info = hat.monitor.common.ComponentInfo(cid=1,
                                                      mid=2,
                                                      name='name',
                                                      group='group',
                                                      address=server_address,
                                                      rank=3,
                                                      blessing=None,
                                                      ready=None)

    async def run_cb(client):
        client.register([
            common.RegisterEvent(
                event_type=('a',),
                source_timestamp=common.now(),
                payload=None)])
        try:
            await asyncio.Future()
        finally:
            await client.register_with_response([
                common.RegisterEvent(
                    event_type=('b'),
                    source_timestamp=common.now(),
                    payload=None)])
            client.register([
                common.RegisterEvent(
                    event_type=('c'),
                    source_timestamp=common.now(),
                    payload=None)])

    monitor_client = MonitorClient()
    server = await create_server(server_address)

    run_future = asyncio.ensure_future(
        hat.event.client.run_client(monitor_client, component_info.group,
                                    run_cb))

    monitor_client.change([component_info._replace(blessing=1, ready=1)])
    conn = await server.get_connection()

    msg = await conn.receive()
    assert msg.data.data[0]['type'] == ['a']

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(conn.receive(), 0.001)

    run_future.cancel()

    msg = await conn.receive()
    assert msg.data.data[0]['type'] == ['b']

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(conn.receive(), 0.001)

    conn.send_register_res(msg.conv, [None])

    msg = await conn.receive()
    assert msg.data.data[0]['type'] == ['c']

    with pytest.raises(asyncio.CancelledError):
        await run_future

    await conn.wait_closed()

    await monitor_client.async_close()
    await server.async_close()
