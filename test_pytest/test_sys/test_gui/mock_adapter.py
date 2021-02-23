from hat import aio
from hat import util
import hat.event.common
import hat.gui.common


json_schema_id = None
json_schema_repo = None


def create_subscription(conf):
    return hat.event.common.Subscription([('a1', '*')])


async def create_adapter(conf, event_client):
    adapter = MockAdapter()
    adapter._event_client = event_client
    adapter._group = aio.Group()
    adapter._sessions = []
    adapter._group.spawn(adapter._event_loop)
    return adapter


class MockAdapter(hat.gui.common.Adapter):

    @property
    def async_group(self):
        return self._group

    async def create_session(self, client):
        session = MockAdapterSession()
        session._adapter_client = client
        session._event_queue = aio.Queue()
        session._group = self._group.create_subgroup()
        client.register_change_cb(session._on_change)
        session._event_client = self._event_client
        session._group.spawn(session._client_loop)
        session._group.spawn(session._event_loop)
        self._sessions.append(session)
        return session

    async def _event_loop(self):
        try:
            while True:
                events = await self._event_client.receive()
                killer = util.first(events,
                                    lambda i: i.event_type == ('a1', 'kill'))
                if killer:
                    break
                for session in self._sessions:
                    session._event_queue.put_nowait(events)
        finally:
            self._group.close()


class MockAdapterSession(hat.gui.common.AdapterSession):

    @property
    def async_group(self):
        return self._group

    def _on_change(self):
        self._event_client.register([hat.event.common.RegisterEvent(
            event_type=('a1', 'action'),
            source_timestamp=None,
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.JSON,
                data=self._adapter_client.remote_data))])

    async def _client_loop(self):
        try:
            while True:
                msg = await self._adapter_client.receive()
                self._event_client.register([hat.event.common.RegisterEvent(
                    event_type=('a1', 'action'),
                    source_timestamp=None,
                    payload=hat.event.common.EventPayload(
                        type=hat.event.common.EventPayloadType.JSON,
                        data=msg))])
        finally:
            self._group.close()

    async def _event_loop(self):
        try:
            while True:
                events = await self._event_queue.get()
                local_data = self._adapter_client.local_data or []
                self._adapter_client.set_local_data(
                    local_data + [e.payload.data for e in events])
                for event in events:
                    await self._adapter_client.send(event.payload.data)
        finally:
            self._group.close()
