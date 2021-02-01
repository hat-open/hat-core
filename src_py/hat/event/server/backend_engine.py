"""Backend engine"""

import importlib
import typing

from hat import aio
from hat import json
from hat.event.server import common


async def create(conf: json.Data) -> 'BackendEngine':
    """Create backend engine

    Args:
        conf: configuration defined by
            ``hat://event/main.yaml#/definitions/backend_engine``

    """
    backend_conf = conf['backend']
    backend_module = importlib.import_module(backend_conf['module'])
    backend = await backend_module.create(backend_conf)

    engine = BackendEngine()
    engine._server_id = conf['server_id']
    engine._backend = backend
    return engine


class BackendEngine(aio.Resource):

    @property
    def async_group(self) -> aio.Resource:
        """Async group"""
        return self._backend.async_group

    async def get_last_event_id(self) -> common.EventId:
        """Get last registered local server's event id"""
        return await self._backend.get_last_event_id(self._server_id)

    async def register(self,
                       process_events: typing.List[common.ProcessEvent]
                       ) -> typing.List[typing.Optional[common.Event]]:
        """Register events"""
        now = common.now()
        events = [common.Event(event_id=process_event.event_id,
                               event_type=process_event.event_type,
                               timestamp=now,
                               source_timestamp=process_event.source_timestamp,
                               payload=process_event.payload)
                  for process_event in process_events]
        return await self._backend.register(events)

    async def query(self,
                    data: common.QueryData
                    ) -> typing.List[common.Event]:
        """Query events"""
        return await self._backend.query(data)
