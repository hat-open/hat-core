"""Event server's communication

Attributes:
    mlog (logging.Logger): module logger

"""

import contextlib
import logging

from hat import aio
from hat import chatter
from hat.event.server import common


mlog = logging.getLogger(__name__)

_source_id = 0


async def create(conf, engine):
    """Create communication

    Args:
        conf (hat.json.Data): configuration defined by
            ``hat://event/main.yaml#/definitions/communication``
        engine (hat.event.module_engine.ModuleEngine): module engine

    Returns:
        Communication

    """
    comm = Communication()
    comm._engine = engine
    comm._async_group = aio.Group(exception_cb=lambda e: mlog.error(
        'exception in communication: %s', e, exc_info=e))
    comm._connection_ids = {}
    comm._subs_registry = common.SubscriptionRegistry()

    chatter_server = await chatter.listen(
        sbs_repo=common.sbs_repo,
        address=conf['address'],
        on_connection_cb=lambda conn: comm._async_group.spawn(
            comm._connection_loop, conn))
    comm._async_group.spawn(aio.call_on_cancel, chatter_server.async_close)
    comm._async_group.spawn(comm._run_engine)
    return comm


class Communication:

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    async def _connection_loop(self, conn):
        global _source_id
        _source_id += 1
        self._connection_ids[conn] = _source_id
        try:
            await self._register_communication_event(_source_id, 'connected')
            while True:
                msg = await conn.receive()
                if msg.data.module != 'HatEvent' or msg.data.type not in [
                        'MsgSubscribe', 'MsgRegisterReq', 'MsgQueryReq']:
                    raise Exception('Message received from client malformed!')
                self._process_msg(msg, conn)
        except chatter.ConnectionClosedError:
            mlog.debug('connection %s closed', _source_id)
        finally:
            await aio.uncancellable(self._close_connection(conn))

    async def _close_connection(self, conn):
        self._subs_registry.remove(conn)
        await conn.async_close()
        source_id = self._connection_ids.pop(conn)
        await self._register_communication_event(source_id, 'disconnected')

    async def _register_communication_event(self, source_id, status):
        source = common.Source(type=common.SourceType.COMMUNICATION,
                               name=None,
                               id=source_id)
        reg_event = common.RegisterEvent(
            event_type=['event', 'communication', status],
            source_timestamp=None,
            payload=None)
        await self._engine.register(source, [reg_event])

    async def _run_engine(self):
        try:
            with self._engine.register_events_cb(self._on_events):
                await self._engine.closed
        finally:
            self._async_group.close()

    def _process_msg(self, msg, conn):
        {'MsgSubscribe': self._process_subscribe,
         'MsgRegisterReq': self._process_register_request,
         'MsgQueryReq': self._process_query_request
         }[msg.data.type](msg, conn)

    def _process_subscribe(self, msg, conn):
        for event_type in msg.data.data:
            self._subs_registry.add(conn, event_type)

    def _process_register_request(self, msg, conn):
        source = common.Source(type=common.SourceType.COMMUNICATION,
                               name=None,
                               id=self._connection_ids[conn])
        events = [common.register_event_from_sbs(i) for i in msg.data.data]
        self._async_group.spawn(self._register_request_response, source,
                                events, conn, msg)

    def _process_query_request(self, msg, conn):
        query = common.query_from_sbs(msg.data.data)
        self._async_group.spawn(self._query_request_response,
                                query, conn, msg)

    async def _register_request_response(self, source, reg_events, conn, msg):
        events = await self._engine.register(source, reg_events)
        if msg.last:
            return
        data = chatter.Data(module='HatEvent',
                            type='MsgRegisterRes',
                            data=[(('event', common.event_to_sbs(e))
                                   if e is not None else ('failure', None))
                                  for e in events])
        conn.send(data, conv=msg.conv)

    async def _query_request_response(self, query, conn, msg):
        events = await self._engine.query(query)
        conn.send(chatter.Data(module='HatEvent',
                               type='MsgQueryRes',
                               data=[common.event_to_sbs(e) for e in events]),
                  conv=msg.conv)

    def _on_events(self, events):
        conn_notify = {}
        for event in events:
            for conn in self._subs_registry.find(event.event_type):
                conn_notify[conn] = (conn_notify.get(conn, []) + [event])
        for conn, notify_events in conn_notify.items():
            with contextlib.suppress(chatter.ConnectionClosedError):
                conn.send(chatter.Data(module='HatEvent',
                                       type='MsgNotify',
                                       data=[common.event_to_sbs(e)
                                             for e in notify_events]))
