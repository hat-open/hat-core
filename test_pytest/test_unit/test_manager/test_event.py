import pytest

from hat import aio
from hat import chatter
from hat import json
from hat import util
from hat.manager import common
import hat.event.common
import hat.manager.devices.event


pytestmark = pytest.mark.asyncio


@pytest.fixture
def addr():
    port = util.get_unused_tcp_port()
    return f'tcp+sbs://127.0.0.1:{port}'


@pytest.fixture
async def server(addr):
    server = Server()
    server._connection_queue = aio.Queue()
    server._srv = await chatter.listen(hat.event.common.sbs_repo,
                                       addr,
                                       server._on_connection)
    try:
        yield server
    finally:
        await server.async_close()


class Server(aio.Resource):

    @property
    def async_group(self):
        return self._srv.async_group

    @property
    def connection_queue(self):
        return self._connection_queue

    def _on_connection(self, conn):
        self._connection_queue.put_nowait(conn)


def create_change_queue(data_storage, path):
    queue = aio.Queue()
    last_value = None

    def on_change(data):
        nonlocal last_value
        new_value = json.get(data, path)
        if new_value == last_value:
            return
        queue.put_nowait(new_value)
        last_value = new_value

    data_storage.register_change_cb(on_change)
    on_change(data_storage.data)
    return queue


def create_register_event(event_type, payload_data, with_payload=True):
    if with_payload:
        payload = hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=payload_data)
    else:
        payload = None

    return hat.event.common.RegisterEvent(event_type=event_type,
                                          source_timestamp=None,
                                          payload=payload)


def create_event(event_type, payload_data):
    event_id = hat.event.common.EventId(123, 321)
    timestamp = hat.event.common.now()
    payload = hat.event.common.EventPayload(
        type=hat.event.common.EventPayloadType.JSON,
        data=payload_data)
    return hat.event.common.Event(event_id=event_id,
                                  event_type=event_type,
                                  timestamp=timestamp,
                                  source_timestamp=None,
                                  payload=payload)


async def test_create(addr, server):
    conf = {'address': addr}
    logger = common.Logger()
    device = hat.manager.devices.event.Device(conf, logger)
    client = await device.create()

    assert client.is_open
    conn = await server.connection_queue.get()
    assert conn.is_open

    await client.async_close()
    await conn.wait_closing()


async def test_set_address():
    conf = {'address': 'addr1'}
    logger = common.Logger()
    device = hat.manager.devices.event.Device(conf, logger)
    assert device.data.data['address'] == 'addr1'

    await device.execute('set_address', 'addr2')
    assert device.data.data['address'] == 'addr2'

    new_conf = device.get_conf()
    assert new_conf['address'] == 'addr2'


@pytest.mark.parametrize('text, register_events', [
    ("""
a/b/c
123
     """, [create_register_event(('a', 'b', 'c'), 123)]),
    ("""
a\\/b/c
     """,
     [create_register_event(('a/b', 'c'), None, False)]),
    ("""
a/b/c
a: 10
===
c/b/a
b: 100
     """,
     [create_register_event(('a', 'b', 'c'), {'a': 10}),
      create_register_event(('c', 'b', 'a'), {'b': 100})]),
])
@pytest.mark.parametrize('with_source_timestamp', [True, False])
async def test_register(addr, server, text, register_events,
                        with_source_timestamp):
    conf = {'address': addr}
    logger = common.Logger()
    device = hat.manager.devices.event.Device(conf, logger)
    client = await device.create()
    conn = await server.connection_queue.get()

    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is True
    assert msg.data.module == 'HatEvent'
    assert msg.data.type == 'MsgSubscribe'
    assert msg.data.data == [['*']]

    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is False
    assert msg.data.module == 'HatEvent'
    assert msg.data.type == 'MsgQueryReq'

    conn.send(chatter.Data('HatEvent', 'MsgQueryRes', []),
              conv=msg.conv)

    await device.execute('register', text, with_source_timestamp)
    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is True
    assert msg.data.module == 'HatEvent'
    assert msg.data.type == 'MsgRegisterReq'

    events = [hat.event.common.register_event_from_sbs(i)
              for i in msg.data.data]

    assert all(((i.source_timestamp is not None) if with_source_timestamp
                else (i.source_timestamp is None))
               for i in events)

    events = [i._replace(source_timestamp=None) for i in events]
    assert events == register_events

    await client.async_close()


async def test_query(addr, server):
    conf = {'address': addr}
    logger = common.Logger()
    device = hat.manager.devices.event.Device(conf, logger)
    latest_queue = create_change_queue(device.data, 'latest')
    client = await device.create()
    conn = await server.connection_queue.get()

    latest = await latest_queue.get()
    assert latest == []

    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is True
    assert msg.data.module == 'HatEvent'
    assert msg.data.type == 'MsgSubscribe'
    assert msg.data.data == [['*']]

    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is False
    assert msg.data.module == 'HatEvent'
    assert msg.data.type == 'MsgQueryReq'

    events = [create_event(('a', 'b', 'c'), 123),
              create_event(('c', 'b', 'a'), 321)]
    data = [hat.event.common.event_to_sbs(event)
            for event in events]
    conn.send(chatter.Data('HatEvent', 'MsgQueryRes', data),
              conv=msg.conv)

    latest = await latest_queue.get()
    assert len(events) == len(latest)

    events = sorted(events, key=lambda i: i.event_type)
    latest = sorted(latest, key=lambda i: i['event_type'])

    for event, i in zip(events, latest):
        assert event.event_id.server == i['event_id']['server']
        assert event.event_id.instance == i['event_id']['instance']
        assert list(event.event_type) == i['event_type']
        assert event.payload.data == i['payload']

    await client.async_close()


async def test_latest(addr, server):
    conf = {'address': addr}
    logger = common.Logger()
    device = hat.manager.devices.event.Device(conf, logger)
    latest_queue = create_change_queue(device.data, 'latest')
    client = await device.create()
    conn = await server.connection_queue.get()

    latest = await latest_queue.get()
    assert latest == []

    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is True
    assert msg.data.module == 'HatEvent'
    assert msg.data.type == 'MsgSubscribe'
    assert msg.data.data == [['*']]

    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is False
    assert msg.data.module == 'HatEvent'
    assert msg.data.type == 'MsgQueryReq'

    conn.send(chatter.Data('HatEvent', 'MsgQueryRes', []),
              conv=msg.conv)

    events = [create_event(('a', 'b', 'c'), 1)]
    data = [hat.event.common.event_to_sbs(event)
            for event in events]
    conn.send(chatter.Data('HatEvent', 'MsgNotify', data),
              conv=msg.conv)

    latest = await latest_queue.get()
    assert len(latest) == 1

    data = util.first(latest, lambda i: i['event_type'] == ['a', 'b', 'c'])
    assert data['payload'] == 1

    events = [create_event(('c', 'b', 'a'), 2)]
    data = [hat.event.common.event_to_sbs(event)
            for event in events]
    conn.send(chatter.Data('HatEvent', 'MsgNotify', data),
              conv=msg.conv)

    latest = await latest_queue.get()
    assert len(latest) == 2

    data = util.first(latest, lambda i: i['event_type'] == ['a', 'b', 'c'])
    assert data['payload'] == 1

    data = util.first(latest, lambda i: i['event_type'] == ['c', 'b', 'a'])
    assert data['payload'] == 2

    events = [create_event(('a', 'b', 'c'), 3)]
    data = [hat.event.common.event_to_sbs(event)
            for event in events]
    conn.send(chatter.Data('HatEvent', 'MsgNotify', data),
              conv=msg.conv)

    latest = await latest_queue.get()
    assert len(latest) == 2

    data = util.first(latest, lambda i: i['event_type'] == ['a', 'b', 'c'])
    assert data['payload'] == 3

    data = util.first(latest, lambda i: i['event_type'] == ['c', 'b', 'a'])
    assert data['payload'] == 2

    await client.async_close()


async def test_changes(addr, server):
    conf = {'address': addr}
    logger = common.Logger()
    device = hat.manager.devices.event.Device(conf, logger)
    changes_queue = create_change_queue(device.data, 'changes')
    client = await device.create()
    conn = await server.connection_queue.get()

    changes = await changes_queue.get()
    assert changes == []

    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is True
    assert msg.data.module == 'HatEvent'
    assert msg.data.type == 'MsgSubscribe'
    assert msg.data.data == [['*']]

    msg = await conn.receive()
    assert msg.first is True
    assert msg.last is False
    assert msg.data.module == 'HatEvent'
    assert msg.data.type == 'MsgQueryReq'

    conn.send(chatter.Data('HatEvent', 'MsgQueryRes', []),
              conv=msg.conv)

    events = [create_event(('a', 'b', 'c'), 1)]
    data = [hat.event.common.event_to_sbs(event)
            for event in events]
    conn.send(chatter.Data('HatEvent', 'MsgNotify', data),
              conv=msg.conv)

    changes = await changes_queue.get()
    assert len(changes) == 1

    data = changes[0]
    assert data['event_type'] == ['a', 'b', 'c']
    assert data['payload'] == 1

    events = [create_event(('c', 'b', 'a'), 2)]
    data = [hat.event.common.event_to_sbs(event)
            for event in events]
    conn.send(chatter.Data('HatEvent', 'MsgNotify', data),
              conv=msg.conv)

    changes = await changes_queue.get()
    assert len(changes) == 2

    data = changes[0]
    assert data['event_type'] == ['c', 'b', 'a']
    assert data['payload'] == 2

    data = changes[1]
    assert data['event_type'] == ['a', 'b', 'c']
    assert data['payload'] == 1

    events = [create_event(('a', 'b', 'c'), 3)]
    data = [hat.event.common.event_to_sbs(event)
            for event in events]
    conn.send(chatter.Data('HatEvent', 'MsgNotify', data),
              conv=msg.conv)

    changes = await changes_queue.get()
    assert len(changes) == 3

    data = changes[0]
    assert data['event_type'] == ['a', 'b', 'c']
    assert data['payload'] == 3

    data = changes[1]
    assert data['event_type'] == ['c', 'b', 'a']
    assert data['payload'] == 2

    data = changes[2]
    assert data['event_type'] == ['a', 'b', 'c']
    assert data['payload'] == 1

    await client.async_close()
