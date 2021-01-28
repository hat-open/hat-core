"""Library used by components for communication with Event Server

This module provides low-level interface (connect/Client) and high-level
interface (run_client) for communication with Event Server.

:func:`connect` is used for establishing single chatter based connection
with Event Server which is represented by :class:`Client`. Once connection
is terminated (signaled with :meth:`Client.closed`), it is up to user to
repeat :func:`connect` call and create new :class:`Client` instance, if
additional communication with Event Server is required.

Example of low-level interface usage::

    client = await hat.event.client.connect('tcp+sbs://127.0.0.1:23012',
                                            [['x', 'y', 'z']])

    registered_events = await client.register_with_response([
        hat.event.common.RegisterEvent(
            event_type=['x', 'y', 'z'],
            source_timestamp=hat.event.common.now(),
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.BINARY,
                data=b'test'))])

    received_events = await client.receive()

    queried_events = await client.query(
        hat.event.common.QueryData(
            event_types=[['x', 'y', 'z']],
            max_results=1))

    assert registered_events == received_events
    assert received_events == queried_events

    await client.async_close()

:func:`run_client` provides high-level interface for continuous communication
with currenty active Event Server based on information obtained from Monitor
Server. This function repeatedly tries to create active connection with
Event Server. When this connection is created, users code is notified by
calling `async_run_cb` callback. Once connection is closed, execution of
`async_run_cb` is cancelled and :func:`run_client` repeats connection
estabishment process.

Example of high-level interface usage::

    async def monitor_async_run():
        await hat.event.client.run_client(
            monitor_client=monitor,
            server_group='event servers',
            async_run_cb=event_async_run])

    async def event_async_run(client):
        while True:
            assert not client.is_closed
            await asyncio.sleep(10)

    monitor = await hat.monitor.client.connect({
        'name': 'client',
        'group': 'test clients',
        'monitor_address': 'tcp+sbs://127.0.0.1:23010',
        'component_address': None})
    await hat.monitor.client.run_component(monitor, monitor_async_run)
    await monitor.async_close()

"""

import asyncio
import contextlib
import logging
import typing

from hat import aio
from hat import chatter
from hat import util
from hat.event import common
import hat.monitor.client


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

reconnect_delay: float = 0.5
"""Delay in seconds before trying to reconnect to event server
(used in high-level interface)"""


async def connect(address: str,
                  subscriptions: typing.List[common.EventType] = [],
                  **kwargs
                  ) -> 'Client':
    """Connect to event server

    For address format see `hat.chatter.connect` coroutine.

    According to Event Server specification, each subscription is event
    type identifier which can contain special subtypes ``?`` and ``*``.
    Subtype ``?`` can occure at any position inside event type identifier
    and is used as replacement for any single subtype. Subtype ``*`` is valid
    only as last subtype in event type identifier and is used as replacement
    for zero or more arbitrary subtypes.

    If subscription is empty list, client doesn't subscribe for any events and
    will not receive server's notifications.

    Args:
        address: event server's address
        subscriptions: subscriptions
        kwargs: additional arguments passed to `hat.chatter.connect` coroutine

    """
    client = Client()
    client._async_group = aio.Group()
    client._conv_futures = {}
    client._event_queue = aio.Queue()

    client._conn = await chatter.connect(common.sbs_repo, address, **kwargs)
    client._async_group.spawn(aio.call_on_cancel, client._conn.async_close)

    if subscriptions:
        client._conn.send(chatter.Data(module='HatEvent',
                                       type='MsgSubscribe',
                                       data=subscriptions))

    client._async_group.spawn(client._receive_loop)
    return client


class Client(aio.Resource):
    """Event Server client

    For creating new client see `connect` coroutine.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def receive(self) -> typing.List[common.Event]:
        """Receive subscribed event notifications

        Raises:
            ConnectionError

        """
        try:
            return await self._event_queue.get()

        except aio.QueueClosedError:
            raise ConnectionError()

    def register(self, events: typing.List[common.RegisterEvent]):
        """Register events

        Raises:
            ConnectionError

        """
        msg_data = chatter.Data(module='HatEvent',
                                type='MsgRegisterReq',
                                data=[common.register_event_to_sbs(i)
                                      for i in events])
        self._conn.send(msg_data)

    async def register_with_response(self,
                                     events: typing.List[common.RegisterEvent]
                                     ) -> typing.List[typing.Optional[common.Event]]:  # NOQA
        """Register events

        Each `common.RegisterEvent` from `events` is paired with results
        `common.Event` if new event was successfuly created or ``None`` is new
        event could not be created.

        Raises:
            ConnectionError

        """
        msg_data = chatter.Data(module='HatEvent',
                                type='MsgRegisterReq',
                                data=[common.register_event_to_sbs(i)
                                      for i in events])
        conv = self._conn.send(msg_data, last=False)
        return await self._wait_conv_res(conv)

    async def query(self,
                    data: common.QueryData
                    ) -> typing.List[common.Event]:
        """Query events from server

        Raises:
            ConnectionError

        """
        msg_data = chatter.Data(module='HatEvent',
                                type='MsgQueryReq',
                                data=common.query_to_sbs(data))
        conv = self._conn.send(msg_data, last=False)
        return await self._wait_conv_res(conv)

    async def _receive_loop(self):
        mlog.debug("starting receive loop")
        try:
            while True:
                mlog.debug("waiting for incoming message")
                msg = await self._conn.receive()
                msg_type = msg.data.module, msg.data.type

                if msg_type == ('HatEvent', 'MsgNotify'):
                    mlog.debug("received event notification")
                    self._process_msg_notify(msg)

                elif msg_type == ('HatEvent', 'MsgQueryRes'):
                    mlog.debug("received query response")
                    self._process_msg_query_res(msg)

                elif msg_type == ('HatEvent', 'MsgRegisterRes'):
                    mlog.debug("received register response")
                    self._process_msg_register_res(msg)

                else:
                    raise Exception("unsupported message type")

        except ConnectionError:
            pass

        except Exception as e:
            mlog.error("read loop error: %s", e, exc_info=e)

        finally:
            mlog.debug("stopping receive loop")
            self._async_group.close()
            self._event_queue.close()
            for f in self._conv_futures.values():
                f.set_exception(ConnectionError())

    async def _wait_conv_res(self, conv):
        if not self.is_open:
            raise ConnectionError()

        response_future = asyncio.Future()
        self._conv_futures[conv] = response_future
        try:
            return await response_future
        finally:
            self._conv_futures.pop(conv, None)

    def _process_msg_notify(self, msg):
        events = [common.event_from_sbs(e) for e in msg.data.data]
        self._event_queue.put_nowait(events)

    def _process_msg_query_res(self, msg):
        f = self._conv_futures.get(msg.conv)
        if not f or f.done():
            return
        events = [common.event_from_sbs(e) for e in msg.data.data]
        f.set_result(events)

    def _process_msg_register_res(self, msg):
        f = self._conv_futures.get(msg.conv)
        if not f or f.done():
            return
        events = [common.event_from_sbs(e) if t == 'event' else None
                  for t, e in msg.data.data]
        f.set_result(events)


async def run_client(monitor_client: hat.monitor.client.Client,
                     server_group: str,
                     async_run_cb: typing.Callable[[Client],
                                                   typing.Awaitable[None]],
                     subscriptions: typing.List[common.EventType] = []
                     ) -> typing.Any:
    """Continuously communicate with currently active Event Server

    This function tries to establish active connection with Event Server
    whithin monitor component group `server_group`. Once this connection is
    established, `async_run_cb` is called with currently active `Client`
    instance. Once connection to Event Server is closed or new active Event
    Server is detected, execution of `async_run_cb` is canceled. If new
    connection to Event Server is successfuly established,
    `async_run_cb` is called with new instance of `Client`.

    `async_run_cb` is called when:
        * new active `Client` is created

    `async_run_cb` execution is cancelled when:
        * `run_client` finishes execution
        * connection to Event Server is closed
        * different active Event Server is detected from Monitor Server's list
          of components

    `run_client` finishes execution when:
        * connection to Monitor Server is closed
        * `async_run_cb` finishes execution (by returning value or raising
          exception, other than `asyncio.CancelledError`)

    Return value of this function is the same as return value of
    `async_run_cb`. If `async_run_cb` finishes by raising exception or if
    connection to Monitor Server is closed, ConnectionError is raised.

    """
    async_group = aio.Group()
    address_queue = aio.Queue()
    async_group.spawn(aio.call_on_done, monitor_client.wait_closing(),
                      address_queue.close)
    async_group.spawn(_address_loop, monitor_client, server_group,
                      address_queue)

    address = None
    try:
        while True:
            while not address:
                address = await address_queue.get_until_empty()

            async with async_group.create_subgroup() as subgroup:
                address_future = subgroup.spawn(address_queue.get_until_empty)
                client_future = subgroup.spawn(_client_loop, subgroup, address,
                                               subscriptions, async_run_cb)

                await asyncio.wait([address_future, client_future],
                                   return_when=asyncio.FIRST_COMPLETED)

                if address_future.done():
                    address = address_future.result()
                else:
                    return client_future.result()

    except aio.QueueClosedError:
        raise ConnectionError()

    finally:
        await aio.uncancellable(async_group.async_close())


async def _address_loop(monitor_client, server_group, address_queue):
    last_address = None
    changes = aio.Queue()

    with monitor_client.register_change_cb(lambda: changes.put_nowait(None)):
        while True:
            info = util.first(monitor_client.components, lambda c: (
                c.group == server_group and
                c.blessing is not None and
                c.blessing == c.ready))
            address = info.address if info else None

            if address != last_address and not address_queue.is_closed:
                mlog.debug("new server address: %s", address)
                last_address = address
                address_queue.put_nowait(address)

            await changes.get()


async def _client_loop(async_group, address, subscriptions, async_run_cb):
    while True:
        async with async_group.create_subgroup() as subgroup:
            mlog.debug("connecting to server %s", address)
            try:
                client = await connect(address, subscriptions)
            except Exception as e:
                mlog.warning("error connecting to server: %s", e, exc_info=e)
                await asyncio.sleep(reconnect_delay)
                continue

            mlog.debug("connected to server - running async_run_cb")
            subgroup.spawn(aio.call_on_cancel, client.async_close)
            subgroup.spawn(aio.call_on_done, client.wait_closing(),
                           subgroup.close)
            run_future = subgroup.spawn(async_run_cb, client)

            await asyncio.wait([run_future])
            with contextlib.suppress(asyncio.CancelledError):
                return run_future.result()

        mlog.debug("connection to server closed")
        await asyncio.sleep(reconnect_delay)
