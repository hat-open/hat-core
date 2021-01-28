import asyncio
import functools

from hat import aio
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
        srv._srv = await juggler.listen(
            '127.0.0.1', port,
            functools.partial(srv._async_group.spawn, srv._connection_loop),
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
        self._async_group.spawn(self._connection_loop, conn)

    async def _server_loop(self):
        try:
            events = await self._client.query(
                common.QueryData(unique_type=True))
            while True:
                self._update_events(events)
                events = await self._client.receive()
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
            'event_type': event_type,
            'timestamp': timestamp,
            'source_timestamp': source_timestamp,
            'payload': payload}
