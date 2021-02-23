import asyncio
import base64

import pytest

from hat import aio
from hat import util
import hat.gui.adapters.latest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def create_event():
    counter = 0

    def create_event(event_type, payload):
        nonlocal counter
        counter += 1
        event_id = hat.event.common.EventId(1, counter)
        event = hat.event.common.Event(event_id=event_id,
                                       event_type=event_type,
                                       timestamp=hat.event.common.now(),
                                       source_timestamp=None,
                                       payload=payload)
        return event

    return create_event


@pytest.fixture
def create_json_event(create_event):

    def create_json_event(event_type, data):
        payload = hat.event.common.EventPayload(
            hat.event.common.EventPayloadType.JSON, data)
        return create_event(event_type, payload)

    return create_json_event


@pytest.fixture
def create_binary_event(create_event):

    def create_binary_event(event_type, data):
        payload = hat.event.common.EventPayload(
            hat.event.common.EventPayloadType.BINARY, data)
        return create_event(event_type, payload)

    return create_binary_event


@pytest.fixture
def create_sbs_event(create_event):

    def create_sbs_event(event_type, sbs_module, sbs_type, sbs_data):
        payload = hat.event.common.EventPayload(
            hat.event.common.EventPayloadType.SBS,
            hat.event.common.SbsData(sbs_module, sbs_type, sbs_data))
        return create_event(event_type, payload)

    return create_sbs_event


class AdapterEventClient(aio.Resource):

    def __init__(self, query_response=[]):
        self._query_response = query_response
        self._async_group = aio.Group()
        self._receive_queue = aio.Queue()
        self._register_queue = aio.Queue()
        self._query_queue = aio.Queue()

    @property
    def async_group(self):
        return self._async_group

    @property
    def receive_queue(self):
        return self._receive_queue

    @property
    def register_queue(self):
        return self._register_queue

    @property
    def query_queue(self):
        return self._query_queue

    async def receive(self):
        return await self._receive_queue.get()

    def register(self, events):
        self._register_queue.put_nowait(events)

    async def register_with_response(self, events):
        self._register_queue.put_nowait(events)
        return [None for _ in events]

    async def query(self, data):
        self._query_queue.put_nowait(data)
        return self._query_response


class AdapterSessionClient(aio.Resource):

    def __init__(self, user, roles):
        self._user = user
        self._roles = roles
        self._local_data = None
        self._local_data_queue = aio.Queue()
        self._receive_queue = aio.Queue()
        self._remote_data = None
        self._change_cbs = util.CallbackRegistry()
        self._async_group = aio.Group()

    @property
    def async_group(self):
        return self._async_group

    @property
    def user(self):
        return self._user

    @property
    def roles(self):
        return self._roles

    @property
    def local_data(self):
        return self._local_data

    @property
    def remote_data(self):
        return self._remote_data

    @property
    def local_data_queue(self):
        return self._local_data_queue

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    def set_local_data(self, data):
        self._local_data = data
        self._local_data_queue.put_nowait(data)

    async def send(self, msg):
        raise NotImplementedError()

    async def receive(self):
        return await self._receive_queue.get()

    def set_remote_data(self, data):
        self._remote_data = data
        self._change_cbs.notify()


async def test_create_subscription():
    conf = {'authorized_roles': [],
            'items': []}
    subscription = await aio.call(hat.gui.adapters.latest.create_subscription,
                                  conf)
    assert list(subscription.get_query_types()) == []

    conf = {'authorized_roles': [],
            'items': [{'key': str(i),
                       'event_type': ('a', str(i))}
                      for i in range(10)]}
    subscription = await aio.call(hat.gui.adapters.latest.create_subscription,
                                  conf)
    for i in range(10):
        assert subscription.matches(('a', str(i)))
        assert not subscription.matches(('b', str(i)))


async def test_create_adapter_empty(create_event):
    conf = {'authorized_roles': [],
            'items': []}
    event_client = AdapterEventClient()
    adapter = await aio.call(hat.gui.adapters.latest.create_adapter,
                             conf, event_client)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(event_client.query_queue.get(), 0.001)

    event_client.receive_queue.put_nowait([create_event(('a', 'b'), None)])

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(adapter.wait_closing(), 0.001)

    await adapter.async_close()
    await event_client.async_close()


async def test_create_adapter_query():
    conf = {'authorized_roles': [],
            'items': [{'key': 'a',
                       'event_type': ['x']},
                      {'key': 'b',
                       'event_type': ['x']},
                      {'key': 'c',
                       'event_type': ['y']}]}
    event_client = AdapterEventClient()
    adapter = await aio.call(hat.gui.adapters.latest.create_adapter,
                             conf, event_client)

    query_data = await event_client.query_queue.get()
    query_event_types = set(query_data.event_types)
    conf_event_types = {tuple(i['event_type']) for i in conf['items']}
    assert query_event_types == conf_event_types

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(event_client.query_queue.get(), 0.001)

    await adapter.async_close()
    await event_client.async_close()


async def test_create_session(create_event):
    conf = {'authorized_roles': ['users'],
            'items': [{'key': 'a',
                       'event_type': ['x']},
                      {'key': 'b',
                       'event_type': ['x']},
                      {'key': 'c',
                       'event_type': ['y']}]}
    event_client = AdapterEventClient()
    adapter = await aio.call(hat.gui.adapters.latest.create_adapter,
                             conf, event_client)

    session_client1 = AdapterSessionClient('user1', ['users'])
    session_client2 = AdapterSessionClient('user2', ['not users'])
    session1 = await adapter.create_session(session_client1)
    session2 = await adapter.create_session(session_client2)

    assert session1.is_open
    assert session2.is_open

    data = await session_client1.local_data_queue.get()
    assert data == {}

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(session_client2.local_data_queue.get(), 0.001)

    event_client.receive_queue.put_nowait([create_event(('x',), None),
                                           create_event(('y',), None),
                                           create_event(('z',), None)])
    data = await session_client1.local_data_queue.get()
    assert set(data.keys()) == {'a', 'b', 'c'}

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(session_client2.local_data_queue.get(), 0.001)

    await session1.async_close()
    await session2.async_close()
    await session_client1.async_close()
    await session_client2.async_close()

    assert adapter.is_open

    await adapter.async_close()
    await event_client.async_close()


async def test_event_payload(create_json_event, create_binary_event,
                             create_sbs_event):

    conf = {'authorized_roles': ['users'],
            'items': [{'key': 'a',
                       'event_type': ['a']}]}
    event_client = AdapterEventClient()
    adapter = await aio.call(hat.gui.adapters.latest.create_adapter,
                             conf, event_client)

    session_client = AdapterSessionClient('user', ['users'])
    session = await adapter.create_session(session_client)

    data = await session_client.local_data_queue.get()
    assert data == {}

    event_client.receive_queue.put_nowait([
        create_json_event(('a',), 123)])
    data = await session_client.local_data_queue.get()
    assert data['a']['payload'] == {'type': 'JSON',
                                    'data': 123}

    base64_data = base64.b64encode(b'123').decode()

    event_client.receive_queue.put_nowait([
        create_binary_event(('a',), b'123')])
    data = await session_client.local_data_queue.get()
    assert data['a']['payload'] == {'type': 'BINARY',
                                    'data': base64_data}

    event_client.receive_queue.put_nowait([
        create_sbs_event(('a',), 'x', 'y', b'123')])
    data = await session_client.local_data_queue.get()
    assert data['a']['payload'] == {'type': 'SBS',
                                    'data': {'module': 'x',
                                             'type': 'y',
                                             'data': base64_data}}

    await session.async_close()
    await session_client.async_close()
    await adapter.async_close()
    await event_client.async_close()
