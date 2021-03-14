import asyncio
import io

from hat import aio
from hat import json
from hat import juggler
from hat import util
from hat.event import client
from hat.event import common


async def create(evt_srv_addr, ui_path):
    srv = Server()
    srv._client = client
    srv._events = {}
    srv._change_cbs = util.CallbackRegistry()
    srv._async_group = aio.Group()

    srv._client = await client.connect(evt_srv_addr, [['*']])
    srv._async_group.spawn(aio.call_on_cancel, srv._client.async_close)
    srv._async_group.spawn(aio.call_on_done, srv._client.wait_closed(),
                           srv._async_group.close)

    try:
        port = util.get_unused_tcp_port()
        srv._addr = f'http://127.0.0.1:{port}'
        srv._srv = await juggler.listen('127.0.0.1', port, srv._on_connection,
                                        static_dir=ui_path)
        srv._async_group.spawn(aio.call_on_cancel, srv._srv.async_close)
        srv._async_group.spawn(aio.call_on_done, srv._srv.wait_closed(),
                               srv._async_group.close)
        srv._async_group.spawn(srv._server_loop)
    except BaseException:
        await aio.uncancellable(srv._async_group.async_close())
        raise

    return srv


class Server(aio.Resource):

    @property
    def async_group(self):
        return self._async_group

    @property
    def addr(self):
        return self._addr

    def _on_connection(self, conn):
        conn = juggler.RpcConnection(conn, {'register': self._act_register})
        self._async_group.spawn(self._connection_loop, conn)

    async def _server_loop(self):
        try:
            events = await self._client.query(
                common.QueryData(unique_type=True))
            while True:
                self._update_events(events)
                events = await self._client.receive()

        except ConnectionError:
            pass

        finally:
            self._async_group.close()

    async def _connection_loop(self, conn):
        with self._change_cbs.register(conn.set_local_data):
            conn.set_local_data(list(self._events.values()))
            await asyncio.Future()

    def _update_events(self, events):
        for event in events:
            self._events[tuple(event.event_type)] = _event_to_json(event)
        self._change_cbs.notify(list(self._events.values()))

    def _act_register(self, text, with_source_timestamp):
        source_timestamp = common.now() if with_source_timestamp else None
        events = list(_parse_register_events(text, source_timestamp))
        if not events:
            return
        self._client.register(events)


def _event_to_json(event):
    event_id = {'server': event.event_id.server,
                'instance': event.event_id.instance}
    event_type = event.event_type
    timestamp = common.timestamp_to_float(event.timestamp)
    source_timestamp = (common.timestamp_to_float(event.source_timestamp)
                        if event.source_timestamp else None)
    if event.payload is None:
        payload = None
    elif event.payload.type == common.EventPayloadType.BINARY:
        payload = 'BINARY'
    elif event.payload.type == common.EventPayloadType.JSON:
        payload = event.payload.data
    elif event.payload.type == common.EventPayloadType.SBS:
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
        payload = (common.EventPayload(common.EventPayloadType.JSON,
                                       json.decode(payload, json.Format.JSON))
                   if payload else None)
        yield common.RegisterEvent(event_type, source_timestamp, payload)
