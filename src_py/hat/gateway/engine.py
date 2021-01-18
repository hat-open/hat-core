"""Gateway engine

Attributes:
    mlog (logging.Logger): module logger

"""

import asyncio
import importlib
import logging

from hat import aio
from hat import util
import hat.event.common
import hat.gateway.common


mlog = logging.getLogger(__name__)


async def create_engine(conf, client):
    """Create engine

    Args:
        conf (hat.json.Data): configuration defined by
            ``hat://gateway/main.yaml#``
        client (hat.event.client.Client): event client

    Returns:
        Engine

    """

    engine = Engine()

    devices = conf['devices']
    if len(set([d['name'] for d in devices])) != len(devices):
        raise Exception("gateway configured with duplicate device names")

    engine._async_group = aio.Group()
    create_proxy_tasks = {
        device_conf['name']: engine._async_group.spawn(
            create_device_proxy, device_conf, client, conf['gateway_name'])
        for device_conf in devices}

    try:
        if create_proxy_tasks:
            await asyncio.wait(create_proxy_tasks.values())
        engine._device_proxies = {}
        for name, task in create_proxy_tasks.items():
            proxy = task.result()
            engine._device_proxies[name] = proxy
            engine._async_group.spawn(engine._wait_closed_proxy, proxy)
            engine._async_group.spawn(aio.call_on_cancel, proxy.async_close)
    except BaseException:
        for task in create_proxy_tasks.values():
            if task.done() and not task.exception():
                engine._async_group.spawn(task.result().asnyc_close)
        await aio.uncancellable(engine._async_group.async_close(cancel=False))
        raise

    engine._async_group.spawn(engine._receive_loop, client)
    return engine


class Engine(aio.Resource):
    """Engine

    For creating new instance of this class see :func:`create_engine`

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def _receive_loop(self, client):
        try:
            while True:
                events = await client.receive()
                for device_name, proxy in self._device_proxies.items():
                    proxy_events = [ev for ev in events
                                    if ev.event_type[3] == device_name]
                    if proxy_events:
                        proxy.add_events(proxy_events)
        except ConnectionError:
            mlog.info('connection to event server closed')
        except asyncio.CancelledError:
            mlog.debug('engine receive loop cancelled')
        finally:
            self._async_group.close()

    async def _wait_closed_proxy(self, proxy):
        try:
            await proxy.wait_closed()
        finally:
            self._async_group.close()

    def _on_exception(self, e):
        mlog.error('uncaught exception in Engine group: %s', e, exc_info=e)


async def create_device_proxy(conf, client, gateway_name):
    """Create device proxy

    Args:
        conf (hat.json.Data): configuration defined by
            ``hat://gateway/main.yaml#/definitions/device``
        client (hat.event.client.Client): event client
        gateway_name (str): gateway name

    Returns:
        DeviceProxy

    """
    proxy = DeviceProxy()
    device_module = importlib.import_module(conf['module'])

    proxy._event_queue = aio.Queue()
    proxy._async_group = aio.Group(proxy._on_exception)
    proxy._client = client
    proxy._device_identifier_prefix = ['gateway', gateway_name,
                                       device_module.device_type, conf['name']]

    enable_event_type = [*proxy._device_identifier_prefix, 'system', 'enable']
    enable_query = hat.event.common.QueryData(event_types=[enable_event_type],
                                              unique_type=True)
    enable_events = await client.query(enable_query)

    enable_event = util.first(
        enable_events, lambda ev: _check_bool_event(ev, enable_event_type))
    enabled = enable_event.payload.data if enable_event is not None else False

    proxy._register_device_running_event(False)
    if enabled:
        await proxy._create_device(conf, device_module)
    else:
        proxy._device = None
        proxy._device_event_client = None

    proxy._async_group.spawn(proxy._idle_loop, conf, device_module, enabled)
    proxy._async_group.spawn(aio.call_on_cancel, proxy._cleanup)

    return proxy


class DeviceProxy(aio.Resource):
    """Device proxy

    For creating new instance of this class see :func:`create_device_proxy`

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    def add_events(self, events):
        """Add newly received events

        Args:
            events (List[hat.event.common.Event]): events

        """
        self._event_queue.put_nowait(events)

    async def _create_device(self, conf, device_module):
        self._device_event_client = _DeviceEventClient(
            self._client, self._async_group.create_subgroup())
        self._device = await device_module.create(
            conf, self._device_event_client, self._device_identifier_prefix)
        self._register_device_running_event(True)

    async def _destroy_device(self):
        await self._device_event_client.async_close()
        await self._device.async_close()
        self._device = None
        self._device_event_client = None
        try:
            self._register_device_running_event(False)
        except ConnectionError:
            mlog.warning('device was destroyed but running event registration '
                         'failed')

    async def _idle_loop(self, conf, device_module, enabled):
        try:
            while True:
                async with self._async_group.create_subgroup() as async_group:
                    new_events_future = async_group.spawn(
                        self._event_queue.get)
                    device_closed_future = (
                        async_group.spawn(self._device.wait_closed)
                        if self._device is not None
                        else asyncio.Future())
                    await asyncio.wait([new_events_future,
                                        device_closed_future],
                                       return_when=asyncio.FIRST_COMPLETED)
                    if self._device and self._device.is_closed:
                        return
                    events = new_events_future.result()

                enable_event_type = [*self._device_identifier_prefix, 'system',
                                     'enable']
                enable_events = [ev for ev in events
                                 if _check_bool_event(ev, enable_event_type)]
                device_events = [ev for ev in events
                                 if ev.event_type != enable_event_type]

                if len(set([ev.payload.data for ev in enable_events])) > 1:
                    mlog.warning(
                        'multiple distinct enable values set for device %s, '
                        'retaining previous enable value (%s)',
                        conf['name'],
                        enabled)
                else:
                    enable_event = util.first(enable_events)
                    enabled = (enable_event.payload.data
                               if enable_event else enabled)

                if enabled and self._device is None:
                    await self._create_device(conf, device_module)
                elif not enabled and self._device is not None:
                    await self._destroy_device()
                elif enabled and self._device is not None:
                    self._device_event_client.add_events(device_events)
        except asyncio.CancelledError:
            mlog.debug('device idle loop cancelled')
        finally:
            self._async_group.close()

    async def _cleanup(self):
        if self._device is not None:
            await self._destroy_device()
        self._event_queue.close()

    def _register_device_running_event(self, is_running):
        self._client.register([hat.event.common.RegisterEvent(
            event_type=[*self._device_identifier_prefix, 'gateway', 'running'],
            source_timestamp=hat.event.common.now(),
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.JSON,
                data=is_running))])

    def _on_exception(self, e):
        mlog.error('device proxy uncaught error: %s', e, exc_info=e)


class _DeviceEventClient(hat.gateway.common.DeviceEventClient, aio.Resource):

    def __init__(self, client, group):
        self._queue = aio.Queue()
        self._client = client
        self._async_group = group
        self._async_group.spawn(aio.call_on_cancel, self._queue.close)

    @property
    def async_group(self):
        """Async group"""
        return self._async_group

    def add_events(self, events):
        """Add newly received events

        Args:
            events (List[hat.event.common.Event]): events

        """
        self._queue.put_nowait(events)

    async def receive(self):
        """See :meth:`hat.gateway.common.DeviceEventClient.receive`"""

        return await self._queue.get()

    def register(self, events):
        """See :meth:`hat.gateway.common.DeviceEventClient.register`"""

        self._client.register(events)

    async def register_with_response(self, events):
        """See
        :meth:`hat.gateway.common.DeviceEventClient.register_with_response`"""

        return await self._client.register_with_response(events)

    async def query(self, data):
        """See :meth:`hat.gateway.common.DeviceEventClient.query`"""

        return await self._client.query(data)

    def _exception_cb(self, e):
        mlog.error('uncaught exception in device event client: %s', e,
                   exc_info=e)


def _check_bool_event(event, event_type):
    if (event.event_type == event_type
            and event.payload is not None
            and isinstance(event.payload.data, bool)):
        return True
    return False
