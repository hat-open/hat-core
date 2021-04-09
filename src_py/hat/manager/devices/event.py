import io
import itertools

from hat import json
from hat.manager import common
import hat.event.client
import hat.event.common


changes_size = 100

default_conf = {'address': 'tcp+sbs://127.0.0.1:23012'}


class Device(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._client = None
        self._data = common.DataStorage({'address': conf['address'],
                                         'latest': [],
                                         'changes': []})

    @property
    def data(self):
        return self._data

    def get_conf(self):
        return {'address': self._data.data['address']}

    async def create(self):
        address = self._data.data['address']
        self._client = await hat.event.client.connect(address, [('*',)])
        self._client.async_group.spawn(self._client_loop, self._client)
        return self._client

    async def execute(self, action, *args):
        if action == 'set_address':
            return self._act_set_address(*args)

        if action == 'register':
            return self._act_register(*args)

        raise ValueError('invalid action')

    async def _client_loop(self, client):
        try:
            latest = []
            changes = []
            self._data.set([], dict(self._data.data,
                                    latest=latest,
                                    changes=changes))

            events = await client.query(
                hat.event.common.QueryData(unique_type=True))
            events = [_event_to_json(event) for event in events]

            latest_cache = {}
            while True:
                if events:
                    for event in events:
                        latest_cache[tuple(event['event_type'])] = event
                    latest = list(latest_cache.values())

                self._data.set([], dict(self._data.data,
                                        latest=latest,
                                        changes=changes))

                events = await self._client.receive()
                events = [_event_to_json(event) for event in events]

                changes = itertools.chain(reversed(events), changes)
                changes = itertools.islice(changes, changes_size)
                changes = list(changes)

        except ConnectionError:
            pass

        finally:
            client.close()

    def _act_set_address(self, address):
        self._logger.log(f'changing address to {address}')
        self._data.set('address', address)

    def _act_register(self, text, with_source_timestamp):
        source_timestamp = (hat.event.common.now() if with_source_timestamp
                            else None)
        events = list(_parse_register_events(text, source_timestamp))

        if not events:
            self._logger.log('register failed - no events')
            return

        if not self._client or not self._client.is_open:
            self._logger.log('register failed - not connected')
            return

        self._logger.log(f'registering events (count: {len(events)})')
        self._client.register(events)


def _event_to_json(event):
    event_id = {'server': event.event_id.server,
                'instance': event.event_id.instance}
    event_type = event.event_type
    timestamp = hat.event.common.timestamp_to_float(event.timestamp)
    source_timestamp = (
        hat.event.common.timestamp_to_float(event.source_timestamp)
        if event.source_timestamp else None)
    if event.payload is None:
        payload = None
    elif event.payload.type == hat.event.common.EventPayloadType.BINARY:
        payload = 'BINARY'
    elif event.payload.type == hat.event.common.EventPayloadType.JSON:
        payload = event.payload.data
    elif event.payload.type == hat.event.common.EventPayloadType.SBS:
        payload = 'SBS'
    else:
        raise ValueError('invalid event payload type')

    return {'event_id': event_id,
            'event_type': list(event_type),
            'timestamp': timestamp,
            'source_timestamp': source_timestamp,
            'payload': payload}


def _parse_register_events(text, source_timestamp):
    reader = io.StringIO(text)
    while line := reader.readline():
        elements = line.split(':', 1)
        event_type = elements[0].strip()
        if not event_type:
            continue
        event_type = tuple(event_type.split('/'))
        payload = elements[1].strip() if len(elements) > 1 else ''
        payload = (
            hat.event.common.EventPayload(
                hat.event.common.EventPayloadType.JSON,
                json.decode(payload, json.Format.JSON))
            if payload else None)
        yield hat.event.common.RegisterEvent(event_type, source_timestamp,
                                             payload)
