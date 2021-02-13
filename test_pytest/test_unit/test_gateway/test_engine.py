import pytest
import asyncio
import collections
import contextlib
import random

import hat.event.common
import hat.event.server.common
import hat.event.client
import hat.event.server.main
import hat.gateway.engine

from hat import aio
from test_unit.test_gateway import mock_device


@pytest.fixture
def event_server_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
async def event_server(event_server_port):
    conf = {
        'backend_engine': {
            'server_id': 1,
            'backend': {
                'module': 'hat.event.server.backends.memory'}},
        'module_engine': {'modules': []},
        'communication': {
            'address': f'tcp+sbs://127.0.0.1:{event_server_port}'}}
    async with aio.Group() as group:
        backend_engine = await hat.event.server.backend_engine.create(
            conf['backend_engine'])
        group.spawn(hat.event.server.main.run, conf, backend_engine)
        await asyncio.sleep(0.01)  # Wait for event server to start
        yield


@pytest.fixture
async def engine_factory(event_server, event_server_port):

    @contextlib.asynccontextmanager
    async def f(gateway_name, devices=[]):
        event_server_address = f'tcp+sbs://127.0.0.1:{event_server_port}'
        conf = {'gateway_name': gateway_name,
                'devices': devices}
        client = await hat.event.client.connect(
            event_server_address, subscriptions=[
                ('gateway', gateway_name, '?', '?', 'system', '*')])
        engine = await hat.gateway.engine.create_engine(conf, client)
        yield engine
        await engine.async_close()
        await client.async_close()

    return f


@pytest.fixture
def device_queue(monkeypatch):

    async def create_wrapper(*args, **kwargs):
        device = await create(*args, **kwargs)
        queue.put_nowait(device)
        return device

    queue = aio.Queue()
    create = mock_device.create
    monkeypatch.setattr(mock_device, 'create', create_wrapper)
    yield queue


async def set_enable(client, gateway_name, device_type, device_name, enable):
    await client.register_with_response([hat.event.common.RegisterEvent(
        event_type=('gateway', gateway_name, device_type, device_name,
                    'system', 'enable'),
        source_timestamp=None,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=enable))])


@pytest.mark.asyncio
async def test_create_engine_without_devices(event_server, engine_factory):
    async with engine_factory('gateway 0', []):
        pass


@pytest.mark.parametrize("device_count", [1, 2, 10])
@pytest.mark.asyncio
async def test_create_device(event_server, event_server_port,
                             engine_factory, device_queue, device_count):
    event_server_address = f'tcp+sbs://127.0.0.1:{event_server_port}'
    client = await hat.event.client.connect(event_server_address)
    device_confs = [{'module': 'test_unit.test_gateway.mock_device',
                     'name': f'mock {i}'} for i in range(device_count)]

    devices = collections.deque()
    async with engine_factory('gateway 0', device_confs):
        for i in device_confs:
            await set_enable(client, 'gateway 0', mock_device.device_type,
                             i['name'], True)
            device = await device_queue.get()
            assert not device.is_closed
            devices.append(device)

        for i in device_confs:
            device = devices.popleft()
            assert not device.is_closed
            await set_enable(client, 'gateway 0', mock_device.device_type,
                             i['name'], False)
            await device.wait_closed()
            assert device.is_closed


@pytest.mark.asyncio
async def test_device_enable(event_server, event_server_port,
                             engine_factory, device_queue):
    event_server_address = f'tcp+sbs://127.0.0.1:{event_server_port}'
    device_type = mock_device.device_type
    device_name = 'mock 0'
    client = await hat.event.client.connect(
        event_server_address, subscriptions=[
            ['gateway', 'gateway 0', device_type, device_name, 'gateway',
             'running']])
    device_confs = [{'module': 'test_unit.test_gateway.mock_device',
                     'name': device_name}]

    async with engine_factory('gateway 0', device_confs):
        assert device_queue.empty()
        running_event = (await client.receive())[0]
        assert running_event.payload.data is False

        await set_enable(client, 'gateway 0', device_type, device_name, True)
        device = await device_queue.get()
        assert not device.is_closed
        running_event = (await client.receive())[0]
        assert running_event.payload.data is True

        await set_enable(client, 'gateway 0', device_type, device_name, False)
        await device.wait_closed()
        assert device.is_closed
        running_event = (await client.receive())[0]
        assert running_event.payload.data is False

        await set_enable(client, 'gateway 0', device_type, device_name, True)
        device = await device_queue.get()
        assert not device.is_closed
        running_event = (await client.receive())[0]
        assert running_event.payload.data is True

    await device.wait_closed()
    assert device.is_closed
    running_event = (await client.receive())[0]
    assert running_event.payload.data is False

    async with engine_factory('gateway 0', device_confs):
        running_event = (await client.receive())[0]
        assert running_event.payload.data is False

        device = await device_queue.get()
        assert not device.is_closed
        running_event = (await client.receive())[0]
        assert running_event.payload.data is True

    await client.async_close()


@pytest.mark.parametrize("device_count", [1, 2, 10])
@pytest.mark.asyncio
async def test_device_client(event_server, event_server_port,
                             engine_factory, device_queue, device_count):
    event_server_address = f'tcp+sbs://127.0.0.1:{event_server_port}'
    device_type = mock_device.device_type
    prefix = ['gateway', 'gateway 0', device_type]
    client = await hat.event.client.connect(
        event_server_address, subscriptions=[
            [*prefix, '?', 'gateway', 'test']])
    device_confs = [{'module': 'test_unit.test_gateway.mock_device',
                     'name': f'mock {i}'} for i in range(device_count)]

    devices = {}
    async with engine_factory('gateway 0', device_confs):
        for i in device_confs:
            await set_enable(client, 'gateway 0', device_type, i['name'], True)
            device = await device_queue.get()
            assert device.event_type_prefix == (*prefix, i['name'])
            devices[i['name']] = device

        # Test receive
        # Predictable shuffle just to make it out-of-order
        # Seed chosen by fair dice roll
        shuffled_names = random.Random(4).sample(list(devices), k=len(devices))
        reg_events = [hat.event.common.RegisterEvent(
            event_type=(*prefix, name, 'system', 'test'),
            source_timestamp=None,
            payload=None
        ) for name in shuffled_names]
        events = await client.register_with_response(reg_events)
        for name, event in zip(shuffled_names, events):
            received = await devices[name].client.receive()
            assert len(received) == 1
            assert received[0] == event

        # Test query
        for device in devices.values():
            result = await device.client.query(hat.event.common.QueryData(
                event_types=[(*prefix, '?', 'system', 'test')]))
            assert ({i.event_type: i for i in events} ==
                    {i.event_type: i for i in result})

        # Test register with response
        for name, device in devices.items():
            event = await device.client.register_with_response([
                hat.event.common.RegisterEvent(
                    event_type=(*prefix, name, 'gateway', 'test'),
                    source_timestamp=hat.event.common.now(),
                    payload=hat.event.common.EventPayload(
                        type=hat.event.common.EventPayloadType.JSON,
                        data=f'{name} test'))])
            assert await client.receive() == event

        # Test register
        for name, device in devices.items():
            reg_event = hat.event.common.RegisterEvent(
                event_type=(*prefix, name, 'gateway', 'test'),
                source_timestamp=None,
                payload=None)
            device.client.register([reg_event])
            received = await client.receive()
            assert len(received) == 1
            event = received[0]
            assert (reg_event.event_type == event.event_type and
                    reg_event.source_timestamp == event.source_timestamp and
                    reg_event.payload == event.payload)


@pytest.mark.parametrize("device_count", [1, 2, 10])
@pytest.mark.asyncio
async def test_device_close(event_server, event_server_port,
                            engine_factory, device_queue, device_count):
    event_server_address = f'tcp+sbs://127.0.0.1:{event_server_port}'
    device_type = mock_device.device_type
    client = await hat.event.client.connect(event_server_address)
    device_confs = [{'module': 'test_unit.test_gateway.mock_device',
                     'name': f'mock {i}'} for i in range(device_count)]

    devices = []
    async with engine_factory('gateway 0', device_confs) as engine:
        for i in device_confs:
            await set_enable(client, 'gateway 0', device_type, i['name'], True)
            devices.append(await device_queue.get())

        #  Close "random" device
        await devices[random.Random(4).randrange(len(devices))].async_close()

        await asyncio.gather(*(i.wait_closed() for i in devices))

        await engine.wait_closed()
        assert engine.is_closed


@pytest.mark.parametrize("register_event", [
    hat.event.common.RegisterEvent(
        event_type=('gateway', 'gateway 0', 'mock', 'mock 0', 'system',
                    'enable'),
        source_timestamp=None,
        payload=None),
    hat.event.common.RegisterEvent(
        event_type=('gateway', 'gateway 0', 'mock', 'mock 0', 'system',
                    'enable'),
        source_timestamp=None,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.BINARY,
            data=b'test')),
    hat.event.common.RegisterEvent(
        event_type=('gateway',),
        source_timestamp=None,
        payload=None),
    hat.event.common.RegisterEvent(
        event_type=('gateway', 'gateway 0'),
        source_timestamp=None,
        payload=None),
    hat.event.common.RegisterEvent(
        event_type=('gateway', 'gateway 0', 'mock'),
        source_timestamp=None,
        payload=None),
    hat.event.common.RegisterEvent(
        event_type=('gateway', 'gateway 0', 'mock', 'mock 0'),
        source_timestamp=None,
        payload=None),
    hat.event.common.RegisterEvent(
        event_type=('gateway', 'gateway 0', 'mock', 'mock 0', 'system',
                    'enable', 'too long'),
        source_timestamp=None,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=False)),
    hat.event.common.RegisterEvent(
        event_type=('gateway', 'gateway 0', 'spock', 'mock 0', 'system',
                    'enable'),
        source_timestamp=None,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=False)),
    hat.event.common.RegisterEvent(
        event_type=('gateway', 'gateway 0', 'mock', 'spock 0', 'system',
                    'enable'),
        source_timestamp=None,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=False)),
    hat.event.common.RegisterEvent(
        event_type=('gateway', 'gateway 0', 'spock', 'mock 0', 'system',
                    'test'),
        source_timestamp=None,
        payload=None),
    hat.event.common.RegisterEvent(
        event_type=('gateway', 'gateway 0', 'mock', 'spock 0', 'system',
                    'test'),
        source_timestamp=None,
        payload=None)])
@pytest.mark.asyncio
async def test_malformed_event(event_server, event_server_port,
                               engine_factory, device_queue, register_event):
    event_server_address = f'tcp+sbs://127.0.0.1:{event_server_port}'
    device_type = mock_device.device_type
    client = await hat.event.client.connect(event_server_address)
    device_confs = [{'module': 'test_unit.test_gateway.mock_device',
                     'name': 'mock 0'}]

    async with engine_factory('gateway 0', device_confs) as engine:
        await set_enable(client, 'gateway 0', device_type, 'mock 0', True)
        device = await device_queue.get()
        await client.register_with_response([register_event])

        await asyncio.sleep(0.1)
        assert not device.is_closed
        assert not engine.is_closed
