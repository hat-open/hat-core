"""Backend engine"""

import importlib

from hat.event.server import common


async def create(conf):
    """Create backend engine

    Args:
        conf (hat.json.Data): configuration defined by
            ``hat://event/main.yaml#/definitions/backend_engine``

    Returns:
        BackendEngine

    """
    backend_conf = conf['backend']
    backend_module = importlib.import_module(backend_conf['module'])
    backend = await backend_module.create(backend_conf)

    engine = BackendEngine()
    engine._server_id = conf['server_id']
    engine._backend = backend
    return engine


class BackendEngine:

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._backend.closed

    async def async_close(self):
        """Async close"""
        await self._backend.async_close()

    async def get_last_event_id(self):
        """Get last registered event id

        Returns:
            common.EventId

        """
        return await self._backend.get_last_event_id(self._server_id)

    async def register(self, events):
        """Register events

        Args:
            events (List[common.ProcessEvent]): process events

        Returns:
            List[Optional[common.Event]]

        """
        now = common.now()
        result = [common.Event(
            event_id=event.event_id,
            event_type=event.event_type,
            timestamp=now,
            source_timestamp=event.source_timestamp,
            payload=event.payload
        ) for event in events]
        await self._backend.register(result)
        return result

    async def query(self, data):
        """Query events

        Args:
            data (common.QueryData): query data

        Returns:
            List[common.Event]

        """
        return await self._backend.query(data)
