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
    engine._new_mappings = {}
    await engine._init_event_type_mappings()
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

        backend_events = [common.BackendEvent(
            event_id=event.event_id,
            event_type_id=self._get_event_type_id(event.event_type),
            timestamp=now,
            source_timestamp=event.source_timestamp,
            payload=event.payload
        ) for event in events]

        if self._new_mappings:
            await self._backend.add_event_type_id_mappings(self._new_mappings)
            self._new_mappings = {}
        await self._backend.register(backend_events)

        return [common.Event(
            event_id=event.event_id,
            event_type=event.event_type,
            timestamp=now,
            source_timestamp=event.source_timestamp,
            payload=event.payload
        ) for event in events]

    async def query(self, data):
        """Query events

        Args:
            data (common.QueryData): query data

        Returns:
            List[common.Event]

        """
        backend_data = common.BackendQueryData(
            event_ids=data.event_ids,
            event_type_ids=(self._query_types_to_ids(data.event_types)
                            if data.event_types is not None else None),
            t_from=data.t_from,
            t_to=data.t_to,
            source_t_from=data.source_t_from,
            source_t_to=data.source_t_to,
            payload=data.payload,
            order=data.order,
            order_by=data.order_by,
            unique_type=data.unique_type,
            max_results=data.max_results)
        events = await self._backend.query(backend_data)

        return [common.Event(
            event_id=event.event_id,
            event_type=self._event_type_from_id(event.event_type_id),
            timestamp=event.timestamp,
            source_timestamp=event.source_timestamp,
            payload=event.payload
        ) for event in events]

    async def _init_event_type_mappings(self):
        mappings = await self._backend.get_event_type_id_mappings()

        self._id_event_type_mapings = mappings
        self._event_type_id_mappings = {tuple(event_type): event_type_id
                                        for event_type_id, event_type
                                        in mappings.items()}
        self._last_event_type_id = max(mappings, default=0)

    def _get_event_type_id(self, event_type):
        if tuple(event_type) in self._event_type_id_mappings:
            return self._event_type_id_mappings[tuple(event_type)]

        self._last_event_type_id += 1
        event_type_id = self._last_event_type_id
        self._event_type_id_mappings[tuple(event_type)] = event_type_id
        self._id_event_type_mapings[event_type_id] = event_type

        self._new_mappings[event_type_id] = event_type

        return event_type_id

    def _event_type_from_id(self, event_type_id):
        return self._id_event_type_mapings[event_type_id]

    def _query_types_to_ids(self, query_types):
        event_type_ids = set()
        for event_type, event_type_id in self._event_type_id_mappings.items():
            match = any(common.matches_query_type(event_type, i)
                        for i in query_types)
            if match:
                event_type_ids.add(event_type_id)
        return list(event_type_ids)
