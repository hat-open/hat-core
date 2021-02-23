"""Latest adapter

This adapter provides latest event for each configured event type.

"""

import base64
import collections

from hat import aio
from hat import util
from hat.gui import common
import hat.event.common


json_schema_id = 'hat://gui/adapters/latest.yaml#'
json_schema_repo = common.json_schema_repo


def create_subscription(conf):
    return hat.event.common.Subscription([tuple(i['event_type'])
                                          for i in conf['items']])


async def create_adapter(conf, client):
    adapter = LatestAdapter()
    adapter._authorized_roles = set(conf['authorized_roles'])
    adapter._client = client
    adapter._change_cbs = util.CallbackRegistry()

    adapter._event_type_keys = {}
    for item in conf['items']:
        event_type = tuple(item['event_type'])
        if event_type not in adapter._event_type_keys:
            adapter._event_type_keys[event_type] = collections.deque()
        adapter._event_type_keys[event_type].append(item['key'])

    if adapter._event_type_keys:
        events = await client.query(hat.event.common.QueryData(
            event_types=[i for i in adapter._event_type_keys],
            unique_type=True))
        adapter._data = dict(adapter._events_to_data(events))
    else:
        adapter._data = {}

    adapter._async_group = aio.Group()
    adapter._async_group.spawn(adapter._run)
    return adapter


class LatestAdapter(common.Adapter):

    @property
    def async_group(self):
        return self._async_group

    async def create_session(self, client):
        roles = set(client.roles)
        is_authorized = not roles.isdisjoint(self._authorized_roles)
        return LatestSession(is_authorized, self, client)

    async def _run(self):
        try:
            while True:
                events = await self._client.receive()
                data = dict(self._events_to_data(events))
                if not data:
                    continue

                self._data = {**self._data, **data}
                self._change_cbs.notify()

        finally:
            self.close()

    def _events_to_data(self, events):
        for event in events:
            for key in self._event_type_keys.get(event.event_type, []):
                yield key, _event_to_data(event)


class LatestSession(common.AdapterSession):

    def __init__(self, is_authorized, adapter, client):
        self._is_authorized = is_authorized
        self._adapter = adapter
        self._client = client
        self._async_group = adapter.async_group.create_subgroup()
        self._async_group.spawn(self._run)

    @property
    def async_group(self):
        return self._async_group

    async def _run(self):
        try:
            if self._is_authorized:
                with self._adapter._change_cbs.register(self._on_change):
                    self._on_change()
                    while True:
                        await self._client.receive()

            else:
                while True:
                    await self._client.receive()

        finally:
            self.close()

    def _on_change(self):
        self._client.set_local_data(self._adapter._data)


def _event_to_data(event):
    timestamp = hat.event.common.timestamp_to_float(event.timestamp)
    source_timestamp = (
        hat.event.common.timestamp_to_float(event.source_timestamp)
        if event.source_timestamp is not None else None)
    return dict(timestamp=timestamp,
                source_timestamp=source_timestamp,
                payload=_event_payload_to_json(event.payload))


def _event_payload_to_json(payload):
    if payload is None:
        return

    if payload.type == hat.event.common.EventPayloadType.JSON:
        return {'type': 'JSON',
                'data': payload.data}

    if payload.type == hat.event.common.EventPayloadType.BINARY:
        return {'type': 'BINARY',
                'data': base64.b64encode(payload.data).decode()}

    if payload.type == hat.event.common.EventPayloadType.SBS:
        return {'type': 'SBS',
                'data': {'module': payload.data.module,
                         'type': payload.data.type,
                         'data': base64.b64encode(payload.data.data).decode()}}

    raise ValueError('unsupported payload type')
