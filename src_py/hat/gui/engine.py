"""GUI engine"""

import collections
import importlib
import logging
import typing

from hat import aio
from hat import json
from hat.gui import common
import hat.event.client


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


async def create_engine(conf: json.Data,
                        client: hat.event.client.Client
                        ) -> 'Engine':
    """Create GUI engine"""
    engine = Engine()
    engine._client = client
    engine._async_group = aio.Group()
    engine._adapters = {}
    engine._adapter_subscriptions = {}
    engine._adapter_clients = {}

    try:
        for adapter_conf in conf['adapters']:
            name = adapter_conf['name']
            if name in engine._adapters:
                raise Exception(f'adapter name {name} not unique')

            module = importlib.import_module(adapter_conf['module'])
            adapter_client = AdapterEventClient(client)

            adapter = await aio.call(module.create_adapter, adapter_conf,
                                     adapter_client)
            engine.async_group.spawn(aio.call_on_cancel, adapter.async_close)
            engine.async_group.spawn(aio.call_on_done, adapter.wait_closing(),
                                     engine.close)

            engine._adapters[name] = adapter
            engine._adapter_subscriptions[name] = await aio.call(
                module.create_subscription, adapter_conf)
            engine._adapter_clients[name] = adapter_client

        engine.async_group.spawn(engine._receive_loop)

    except BaseException:
        await aio.uncancellable(engine.async_close())
        raise

    return engine


class Engine(aio.Resource):
    """GUI engine"""

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def adapters(self) -> typing.Dict[str, common.Adapter]:
        """Adapters"""
        return self._adapters

    async def _receive_loop(self):
        try:
            while True:
                events = await self._client.receive()
                adapter_events = {}

                for event in events:
                    adapter_subscriptions = self._adapter_subscriptions.items()
                    for name, subscription in adapter_subscriptions:
                        if not subscription.matches(event.event_type):
                            continue
                        if name not in adapter_events:
                            adapter_events[name] = collections.deque()
                        adapter_events[name].append(event)

                for name, events in adapter_events.items():
                    adapter_client = self._adapter_clients[name]
                    adapter_client.receive_queue.put_nowait(list(events))

        except aio.QueueClosedError:
            pass

        except Exception as e:
            mlog.error('read loop error: %s', e, exc_info=e)

        finally:
            self.close()


class AdapterEventClient(common.AdapterEventClient):

    def __init__(self, client: hat.event.client.Client):
        self._client = client
        self._receive_queue = aio.Queue()
        self.async_group.spawn(aio.call_on_cancel, self._receive_queue.close)

    @property
    def async_group(self) -> aio.Group:
        return self._client.async_group

    @property
    def receive_queue(self) -> aio.Queue:
        return self._receive_queue

    async def receive(self) -> typing.List[hat.event.common.Event]:
        try:
            return await self._receive_queue.get()

        except aio.QueueClosedError:
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
