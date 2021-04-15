"""Gateway engine"""

import collections
import contextlib
import importlib
import logging
import typing

from hat import aio
from hat import json
from hat.gateway import common
import hat.event.client
import hat.event.common


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


async def create_engine(conf: json.Data,
                        client: hat.event.client.Client
                        ) -> 'Engine':
    """Create gateway engine"""
    gateway_name = conf['gateway_name']

    engine = Engine()
    engine._client = client
    engine._async_group = aio.Group()
    engine._devices = {}

    try:
        for device_conf in conf['devices']:
            device = DeviceProxy(device_conf, client, gateway_name)
            engine.async_group.spawn(aio.call_on_cancel, device.async_close)
            engine.async_group.spawn(aio.call_on_done, device.wait_closing(),
                                     engine.close)

            key = device.device_type, device.name
            if key in engine._devices:
                raise Exception('duplicate device identifier: %s', key)
            engine._devices[key] = device

        if engine._devices:
            enable_event_types = [('gateway', gateway_name, device.device_type,
                                   device.name, 'system', 'enable')
                                  for device in engine._devices.values()]
            enable_query = hat.event.common.QueryData(
                event_types=enable_event_types,
                unique_type=True)
            enable_events = await client.query(enable_query)

        else:
            enable_events = []

        for event in enable_events:
            if not _is_enable_event(event):
                continue
            key = event.event_type[2:4]
            device = engine._devices.get(key)
            if device:
                device.set_enabled(True)

        engine.async_group.spawn(engine._read_loop)

    except BaseException:
        await aio.uncancellable(engine.async_close())
        raise

    return engine


class Engine(aio.Resource):
    """Gateway engine"""

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def _read_loop(self):
        try:
            while True:
                events = await self._client.receive()
                device_events = {}

                for event in events:
                    key = event.event_type[2:4]
                    device = self._devices.get(key)

                    if not device:
                        continue

                    elif event.event_type[5:] == ('enable',):
                        device.set_enabled(_is_enable_event(event))

                    elif device.enabled:
                        if device not in device_events:
                            device_events[device] = collections.deque()
                        device_events[device].append(event)

                for device, events in device_events.items():
                    device.client.receive_queue.put_nowait(list(events))

        except ConnectionError:
            pass

        except Exception as e:
            mlog.error('read loop error: %s', e, exc_info=e)

        finally:
            self.close()


def _is_enable_event(event):
    return (event.payload and
            event.payload.type == hat.event.common.EventPayloadType.JSON and
            event.payload.data is True)


class DeviceProxy(aio.Resource):
    """Device proxy"""

    def __init__(self,
                 conf: json.Data,
                 client: hat.event.client.Client,
                 gateway_name: str):
        self._conf = conf
        self._async_group = aio.Group()
        self._enabled_queue = aio.Queue()
        self._enabled = False
        self._client = DeviceEventClient(client)
        self._device_module = importlib.import_module(conf['module'])
        self._event_type_prefix = ('gateway', gateway_name,
                                   self._device_module.device_type,
                                   conf['name'])
        self._async_group.spawn(self._enable_loop)

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def device_type(self) -> str:
        """Device type"""
        return self._device_module.device_type

    @property
    def name(self) -> str:
        """Device name"""
        return self._conf['name']

    @property
    def enabled(self) -> bool:
        """Enabled flag"""
        return self._enabled

    @property
    def client(self) -> 'DeviceEventClient':
        """Device's event client"""
        return self._client

    def set_enabled(self, enabled: bool):
        """Set enable flag"""
        if enabled == self._enabled:
            return

        self._enabled_queue.put_nowait(enabled)
        self._enabled = enabled

    async def _enable_loop(self):
        enabled = False
        is_running = False
        try:
            self._register_running(False)
            while True:
                while not enabled:
                    enabled = await self._enabled_queue.get_until_empty()

                async with self._async_group.create_subgroup() as subgroup:
                    device = await subgroup.spawn(aio.call,
                                                  self._device_module.create,
                                                  self._conf, self._client,
                                                  self._event_type_prefix)
                    subgroup.spawn(aio.call_on_cancel, device.async_close)
                    subgroup.spawn(aio.call_on_done, device.wait_closing(),
                                   subgroup.close)

                    self._register_running(True)
                    is_running = True

                    while enabled:
                        enabled = await subgroup.spawn(
                            self._enabled_queue.get_until_empty)

                self._register_running(False)
                is_running = False

        except ConnectionError:
            pass

        except Exception as e:
            mlog.error('enable loop error: %s', e, exc_info=e)

        finally:
            self._enabled = False
            self._enabled_queue.close()
            self.client.receive_queue.close()
            self.close()

            if is_running:
                with contextlib.suppress(Exception):
                    self._register_running(False)

    def _register_running(self, is_running):
        self._client.register([hat.event.common.RegisterEvent(
            event_type=(*self._event_type_prefix, 'gateway', 'running'),
            source_timestamp=hat.event.common.now(),
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.JSON,
                data=is_running))])


class DeviceEventClient(common.DeviceEventClient):

    def __init__(self, client: hat.event.client.Client):
        self._client = client
        self._receive_queue = aio.Queue()

    @property
    def async_group(self) -> aio.Group:
        return self._client.async_group

    @property
    def receive_queue(self) -> aio.Queue:
        return self._receive_queue

    async def receive(self) -> typing.List[hat.event.common.Event]:
        try:
            return await self._receive_queue.get()

        except ConnectionError:
            raise ConnectionError()

    def register(self, events: typing.List[hat.event.common.RegisterEvent]):
        self._client.register(events)

    async def register_with_response(self,
                                     events: typing.List[hat.event.common.RegisterEvent]  # NOQA
                                     ) -> typing.List[typing.Optional[hat.event.common.Event]]:  # NOQA
        return await self._client.register_with_response(events)

    async def query(self,
                    data: hat.event.common.QueryData
                    ) -> typing.List[hat.event.common.Event]:
        return await self._client.query(data)
