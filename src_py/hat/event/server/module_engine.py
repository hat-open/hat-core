"""Module engine"""

import asyncio
import collections
import importlib
import logging
import typing

from hat import aio
from hat import json
from hat import util
from hat.event.server import common
import hat.event.server.backend_engine


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


async def create(conf: json.Data,
                 backend_engine: hat.event.server.backend_engine.BackendEngine
                 ) -> 'ModuleEngine':
    """Create module engine

    Args:
        conf: configuration defined by
            ``hat://event/main.yaml#/definitions/module_engine``
        backend_engine: backend engine

    """
    engine = ModuleEngine()
    engine._backend = backend_engine
    engine._async_group = aio.Group()
    engine._register_queue = aio.Queue()
    engine._register_cbs = util.CallbackRegistry()

    last_event_id = await engine._backend.get_last_event_id()
    engine._server_id = last_event_id.server
    engine._last_instance_id = last_event_id.instance

    engine._modules = []
    for module_conf in conf['modules']:
        py_module = importlib.import_module(module_conf['module'])
        module = await py_module.create(module_conf, engine)
        engine._async_group.spawn(aio.call_on_cancel,
                                  module.async_close)
        engine._modules.append(module)

    engine._async_group.spawn(engine._register_loop)

    for module in engine._modules:
        engine._async_group.spawn(aio.call_on_done, module.wait_closing(),
                                  engine.close)

    return engine


class ModuleEngine(aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    def register_events_cb(self,
                           cb: typing.Callable[[typing.List[common.Event]],
                                               None]
                           ) -> util.RegisterCallbackHandle:
        """Register events callback"""
        return self._register_cbs.register(cb)

    def create_process_event(self,
                             source: common.Source,
                             event: common.RegisterEvent
                             ) -> common.ProcessEvent:
        """Create process event"""
        self._last_instance_id += 1
        return common.ProcessEvent(
            event_id=common.EventId(
                server=self._server_id,
                instance=self._last_instance_id),
            source=source,
            event_type=event.event_type,
            source_timestamp=event.source_timestamp,
            payload=event.payload)

    async def register(self,
                       source: common.Source,
                       events: typing.List[common.RegisterEvent]
                       ) -> typing.List[typing.Optional[common.Event]]:
        """Register events"""
        if not events:
            return []
        future = asyncio.Future()
        self._register_queue.put_nowait((future, source, events))
        return await future

    async def query(self,
                    data: common.QueryData
                    ) -> typing.List[common.Event]:
        """Query events"""
        return await self._backend.query(data)

    async def _register_loop(self):
        future = None
        mlog.debug("starting register loop")
        try:
            while True:
                mlog.debug("waiting for register requests")
                future, source, register_events = \
                    await self._register_queue.get()

                mlog.debug("processing register requests")
                initial_events = [self.create_process_event(source, i)
                                  for i in register_events]

                process_events = await self._process_sessions(initial_events)

                events = await self._backend.register(process_events)

                result = events[:len(initial_events)]
                future.set_result(result)

                events = [event for event in events if event]
                if events:

                    self._register_cbs.notify(events)

        except Exception as e:
            mlog.error("register loop error: %s", e, exc_info=e)

        finally:
            mlog.debug("register loop closed")
            self._async_group.close()
            self._register_queue.close()

            if future and not future.done():
                future.set_exception(Exception('module engine closed'))

            while not self._register_queue.empty():
                future, _, __ = self._register_queue.get_nowait()
                future.set_exception(Exception('module engine closed'))

    async def _process_sessions(self, events):
        all_events = collections.deque()

        async with self._async_group.create_subgroup() as subgroup:
            module_sessions = collections.deque()
            for module in self._modules:
                session = await subgroup.spawn(module.create_session)
                module_sessions.append((module, session))

                subgroup.spawn(aio.call_on_cancel, session.async_close)
                subgroup.spawn(aio.call_on_done, session.wait_closing(),
                               subgroup.close)

            while events:
                all_events.extend(events)
                new_events = collections.deque()

                for module, session in module_sessions:
                    filtered_events = [
                        event for event in events
                        if module.subscription.matches(event.event_type)]
                    if not filtered_events:
                        continue

                    result = await subgroup.spawn(session.process,
                                                  filtered_events)
                    new_events.extend(result)

                events = new_events

        return list(all_events)
