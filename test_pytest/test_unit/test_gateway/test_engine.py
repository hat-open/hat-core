import asyncio
import importlib
import itertools
import sys
import types

import pytest

from hat import aio
import hat.event.common
import hat.gateway.engine


pytestmark = pytest.mark.asyncio


gateway_name = 'gateway_name'
device_type = 'device_type'


@pytest.fixture
def device_module():
    for i in itertools.count(1):
        module_name = f'{device_type}_{i}'
        if module_name not in sys.modules:
            break

    module = types.ModuleType(module_name)
    module.device_type = device_type
    module.json_schema_id = None
    module.json_schema_repo = None
    module.create = Device
    sys.modules[module_name] = module

    try:
        yield module_name

    finally:
        del sys.modules[module_name]


@pytest.fixture
def device_queue(device_module, monkeypatch):
    queue = aio.Queue()

    def create(conf, client, prefix):
        device = Device(conf, client, prefix)
        queue.put_nowait(device)
        return device

    module = importlib.import_module(device_module)
    monkeypatch.setattr(module, 'create', create)
    return queue


@pytest.fixture
def create_event():
    counter = 0

    def create_event(event_type, payload_data):
        nonlocal counter
        counter += 1
        event_id = hat.event.common.EventId(1, counter)
        payload = create_json_payload(payload_data)
        event = hat.event.common.Event(event_id=event_id,
                                       event_type=event_type,
                                       timestamp=hat.event.common.now(),
                                       source_timestamp=None,
                                       payload=payload)
        return event

    return create_event


@pytest.fixture
def create_enable_event(create_event):

    def create_enable_event(device_name, is_enabled):
        event_type = ('gateway', gateway_name, device_type, device_name,
                      'system', 'enable')
        return create_event(event_type, is_enabled)

    return create_enable_event


def create_json_payload(data):
    return hat.event.common.EventPayload(
        hat.event.common.EventPayloadType.JSON, data)


class EventClient(aio.Resource):

    def __init__(self, query_result=[]):
        self._query_result = query_result
        self._receive_queue = aio.Queue()
        self._register_queue = aio.Queue()
        self._query_queue = aio.Queue()
        self._async_group = aio.Group()
        self._async_group.spawn(aio.call_on_cancel, self._receive_queue.close)

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
        try:
            return await self._receive_queue.get()
        except aio.QueueClosedError:
            raise ConnectionError()

    def register(self, events):
        self._register_queue.put_nowait(events)

    async def register_with_response(self, events):
        self._register_queue.put_nowait(events)
        return [None for _ in events]

    async def query(self, data):
        self._query_queue.put_nowait(data)
        return self._query_result


class Device(aio.Resource):

    def __init__(self, conf, client, prefix):
        self._conf = conf
        self._client = client
        self._prefix = prefix
        self._async_group = aio.Group()

    @property
    def async_group(self):
        return self._async_group

    @property
    def conf(self):
        return self._conf

    @property
    def client(self):
        return self._client

    @property
    def prefix(self):
        return self._prefix


async def test_empty_engine():
    conf = {'gateway_name': gateway_name,
            'devices': []}
    client = EventClient()
    engine = await hat.gateway.engine.create_engine(conf, client)

    assert client.query_queue.empty()
    assert client.register_queue.empty()

    await engine.async_close()
    await client.async_close()


@pytest.mark.parametrize("device_count", [1, 2, 5])
async def test_create_engine_with_disabled_devices(device_module, device_queue,
                                                   device_count):
    device_names = [f'name{i}' for i in range(device_count)]
    conf = {'gateway_name': gateway_name,
            'devices': [{'module': device_module,
                         'name': name}
                        for name in device_names]}
    client = EventClient()

    engine = await hat.gateway.engine.create_engine(conf, client)
    data = await client.query_queue.get()
    subscription = hat.event.common.Subscription(data.event_types)
    for device_name in device_names:
        event_type = ('gateway', gateway_name, device_type, device_name,
                      'system', 'enable')
        assert subscription.matches(event_type)

    assert device_queue.empty()

    await engine.async_close()
    await client.async_close()


@pytest.mark.parametrize("device_count", [1, 2, 5])
async def test_create_engine_with_enabled_devices(device_module, device_queue,
                                                  create_enable_event,
                                                  device_count):
    device_names = [f'name{i}' for i in range(device_count)]
    conf = {'gateway_name': gateway_name,
            'devices': [{'module': device_module,
                         'name': name}
                        for name in device_names]}
    client = EventClient([create_enable_event(device_name, True)
                          for device_name in device_names])

    engine = await hat.gateway.engine.create_engine(conf, client)

    devices = []
    for _ in range(device_count):
        device = await device_queue.get()
        a, b, c, d = device.prefix
        assert a == 'gateway'
        assert b == gateway_name
        assert c == device_type
        assert d in device_names
        devices.append(device)

    assert engine.is_open
    for device in devices:
        assert device.is_open

    await engine.async_close()
    await client.async_close()
    for device in devices:
        assert device.is_closed


async def test_close_engine_when_device_closed(device_module, device_queue,
                                               create_enable_event):
    device_name = 'name'
    conf = {'gateway_name': gateway_name,
            'devices': [{'module': device_module,
                         'name': device_name}]}
    client = EventClient([create_enable_event(device_name, True)])

    engine = await hat.gateway.engine.create_engine(conf, client)
    device = await device_queue.get()

    assert device.is_open
    assert engine.is_open

    await device.async_close()
    await engine.wait_closed()
    await client.async_close()


async def test_enable_disable(device_module, device_queue,
                              create_enable_event):
    device_name = 'name'
    conf = {'gateway_name': gateway_name,
            'devices': [{'module': device_module,
                         'name': device_name}]}
    client = EventClient([])

    engine = await hat.gateway.engine.create_engine(conf, client)
    assert device_queue.empty()

    client.receive_queue.put_nowait([create_enable_event(device_name, True)])
    device = await device_queue.get()

    assert engine.is_open
    assert device.is_open

    client.receive_queue.put_nowait([create_enable_event(device_name, True)])
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(device_queue.get(), 0.001)

    assert engine.is_open
    assert device.is_open

    client.receive_queue.put_nowait([create_enable_event(device_name, False)])

    await device.wait_closed()
    assert engine.is_open

    client.receive_queue.put_nowait([create_enable_event(device_name, True)])
    device = await device_queue.get()

    assert engine.is_open
    assert device.is_open

    await device.async_close()
    await engine.async_close()
    await client.async_close()

    assert device_queue.empty()


async def test_running_event(device_module, create_enable_event):
    device_name = 'name'
    running_event_type = ('gateway', gateway_name, device_type, device_name,
                          'gateway', 'running')
    conf = {'gateway_name': gateway_name,
            'devices': [{'module': device_module,
                         'name': device_name}]}
    client = EventClient([create_enable_event(device_name, False)])

    engine = await hat.gateway.engine.create_engine(conf, client)
    events = await client.register_queue.get()

    assert len(events) == 1
    assert events[0].event_type == running_event_type
    assert events[0].payload == create_json_payload(False)

    client.receive_queue.put_nowait([create_enable_event(device_name, True)])
    events = await client.register_queue.get()

    assert len(events) == 1
    assert events[0].event_type == running_event_type
    assert events[0].payload == create_json_payload(True)

    client.receive_queue.put_nowait([create_enable_event(device_name, False)])
    events = await client.register_queue.get()

    assert len(events) == 1
    assert events[0].event_type == running_event_type
    assert events[0].payload == create_json_payload(False)

    client.receive_queue.put_nowait([create_enable_event(device_name, True)])
    events = await client.register_queue.get()

    assert len(events) == 1
    assert events[0].event_type == running_event_type
    assert events[0].payload == create_json_payload(True)

    await engine.async_close()
    events = await client.register_queue.get()

    assert len(events) == 1
    assert events[0].event_type == running_event_type
    assert events[0].payload == create_json_payload(False)

    await client.async_close()


async def test_device_event_client_receive(device_module, device_queue,
                                           create_enable_event, create_event):
    device_name = 'name'
    conf = {'gateway_name': gateway_name,
            'devices': [{'module': device_module,
                         'name': device_name}]}
    client = EventClient([create_enable_event(device_name, True)])

    engine = await hat.gateway.engine.create_engine(conf, client)
    device = await device_queue.get()
    assert device.client.is_open

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(device.client.receive(), 0.001)

    event_type = ('gateway', gateway_name, device_type, device_name,
                  'system', 'abc')
    event = create_event(event_type, 123)
    client.receive_queue.put_nowait([event])

    result = await device.client.receive()
    assert result == [event]

    event_type = ('gateway', gateway_name, device_type, f'not_{device_name}',
                  'system', 'abc')
    event = create_event(event_type, 123)
    client.receive_queue.put_nowait([event])

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(device.client.receive(), 0.001)

    await device.async_close()
    await engine.async_close()
    await client.async_close()


async def test_device_event_client_query(device_module, device_queue,
                                         create_enable_event):
    device_name = 'name'
    conf = {'gateway_name': gateway_name,
            'devices': [{'module': device_module,
                         'name': device_name}]}
    query_result = [create_enable_event(device_name, True)]
    client = EventClient(query_result)

    engine = await hat.gateway.engine.create_engine(conf, client)
    await client.query_queue.get()
    device = await device_queue.get()
    assert client.query_queue.empty()

    query_data = hat.event.common.QueryData()
    result = await device.client.query(query_data)
    assert result == query_result

    result = await client.query_queue.get()
    assert result == query_data
    assert client.query_queue.empty()

    await device.async_close()
    await engine.async_close()
    await client.async_close()


async def test_device_event_client_register(device_module, device_queue,
                                            create_enable_event, create_event):
    device_name = 'name'
    running_event_type = ('gateway', gateway_name, device_type, device_name,
                          'gateway', 'running')
    conf = {'gateway_name': gateway_name,
            'devices': [{'module': device_module,
                         'name': device_name}]}
    client = EventClient([create_enable_event(device_name, True)])

    engine = await hat.gateway.engine.create_engine(conf, client)
    device = await device_queue.get()
    result = await client.register_queue.get()

    assert len(result) == 1
    assert result[0].event_type == running_event_type
    assert result[0].payload == create_json_payload(False)

    event = create_event(('a', 'b', 'c'), 123)
    device.client.register([event])

    result = await client.register_queue.get()
    assert result == [event]

    event = create_event(('a', 'b', 'c'), 321)
    result = await device.client.register_with_response([event])
    assert result == [None]

    result = await client.register_queue.get()
    assert result == [event]

    await device.async_close()
    await engine.async_close()
    await client.async_close()


async def test_create_duplicate_device_identifiers(device_module):
    device_name = 'name'
    conf = {'gateway_name': gateway_name,
            'devices': [{'module': device_module,
                         'name': device_name},
                        {'module': device_module,
                         'name': device_name}]}
    client = EventClient()

    with pytest.raises(Exception):
        await hat.gateway.engine.create_engine(conf, client)

    await client.async_close()
