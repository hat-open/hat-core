"""Module engine"""

import asyncio
import importlib
import logging

from hat import aio
from hat import util
from hat.event.server import common


mlog = logging.getLogger(__name__)


class ModuleEngineClosedError(Exception):
    """Error signaling closed module engine"""


async def create(conf, backend_engine):
    """Create module engine

    Args:
        conf (hat.json.Data): configuration defined by
            ``hat://event/main.yaml#/definitions/module_engine``
        backend_engine (hat.event.backend_engine.BackendEngine): backend engine

    Returns:
        ModuleEngine

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

    return engine


class ModuleEngine:

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    def register_events_cb(self, cb):
        """Register events callback

        Args:
            cb (Callable[[List[common.Event]],None]): change callback

        Returns:
            util.RegisterCallbackHandle

        """
        return self._register_cbs.register(cb)

    def create_process_event(self, source, event):
        """Create process event

        Args:
            source (common.Source): event source
            event (common.RegisterEvent): register event

        Returns:
            common.ProcessEvent

        """
        self._last_instance_id += 1
        return common.ProcessEvent(
            event_id=common.EventId(
                server=self._server_id,
                instance=self._last_instance_id),
            source=source,
            event_type=event.event_type,
            source_timestamp=event.source_timestamp,
            payload=event.payload)

    async def register(self, source, events):
        """Register events

        Args:
            source (common.Source): event source
            events (List[common.RegisterEvent]): register events

        Returns:
            List[Optional[common.Event]]

        Raises:
            ModuleEngineClosedError
            Exception

        """
        if self.closed.done():
            raise ModuleEngineClosedError()
        if not events:
            return []
        future = asyncio.Future()
        self._register_queue.put_nowait((future, source, events))
        return await future

    async def query(self, data):
        """Query events

        Args:
            data (common.QueryData): query data

        Returns:
            List[common.Event]

        Raises:
            ModuleEngineClosedError
            Exception

        """
        if self.closed.done():
            raise ModuleEngineClosedError()
        return await self._backend.query(data)

    async def _register_loop(self):
        future = None
        try:
            while True:
                future, source, register_events = \
                    await self._register_queue.get()

                process_events = [self.create_process_event(source, i)
                                  for i in register_events]

                global_changes = common.SessionChanges(
                    new=list(process_events), deleted=[])
                module_sessions = [await _create_module_session(i)
                                   for i in self._modules]
                for i in module_sessions:
                    await i.add_changes(global_changes)

                while True:
                    try:
                        futures = (i.process() for i in module_sessions)
                        session_changes = await asyncio.gather(*futures)
                    except Exception as e:
                        for f in futures:
                            f.cancel()
                        mlog.error('session process error %s',
                                   e, exc_info=e)
                        raise

                    for i, changes in enumerate(session_changes):
                        if not changes:
                            continue
                        global_changes.new.extend(changes.new)
                        global_changes.deleted.extend(changes.deleted)

                        for j, session in enumerate(module_sessions):
                            if i != j:
                                await session.add_changes(changes)

                    if not any(i.has_pending_changes for i in module_sessions):
                        break

                deleted_ids = {i.event_id for i in global_changes.deleted}
                all_process_events = [i for i in global_changes.new
                                      if i.event_id not in deleted_ids]

                events = await self._backend.register(all_process_events)

                for session in module_sessions:
                    await session.async_close(events)

                event_ids = {event.event_id: event
                             for event in events
                             if event}
                result = [event_ids[i.event_id] for i in process_events
                          if i.event_id in event_ids]
                future.set_result(result)
                self._register_cbs.notify(events)
        except BaseException as e:
            if future and not future.done():
                future.set_exception(e)
            while not self._register_queue.empty():
                future, _, __ = self._register_queue.get_nowait()
                future.set_exception(e)
        finally:
            self._register_queue.close()
            self._async_group.close()


async def _create_module_session(module):
    session = _ModuleSession()
    session._module = module
    session._session = await module.create_session()
    session._pending_changes = common.SessionChanges(new=[], deleted=[])
    return session


class _ModuleSession():

    async def async_close(self, events):
        await self._session.async_close(events)

    @property
    def has_pending_changes(self):
        return self._pending_changes.new or self._pending_changes.deleted

    async def process(self):
        if self._pending_changes != common.SessionChanges(new=[], deleted=[]):
            changes = await self._session.process(self._pending_changes)
            self._pending_changes = common.SessionChanges(new=[], deleted=[])
        else:
            changes = common.SessionChanges(new=[], deleted=[])
        return changes

    async def add_changes(self, changes):
        for name in ['new', 'deleted']:
            for event in getattr(changes, name):
                match = any(common.matches_query_type(event.event_type, i)
                            for i in self._module.subscriptions)
                if not match:
                    continue
                getattr(self._pending_changes, name).append(event)
