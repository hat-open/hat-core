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

    async def monitor_async_run(monitor):
        await hat.event.client.run_client(
            monitor_client=monitor,
            server_group='event servers',
            async_run_cb=event_async_run])

    async def event_async_run(client):
        while True:
            assert not client.closed.done()
            await asyncio.sleep(10)

    await hat.monitor.client.run_component(
        conf={'name': 'client',
              'group': 'test clients',
              'monitor_address': 'tcp+sbs://127.0.0.1:23010',
              'component_address': None},
        async_run_cb=monitor_async_run)


Attributes:
    mlog (logging.Logger): module logger
    reconnect_delay (int): delay in seconds before trying to reconnect to
        event server (used in high-level interface)

"""

import asyncio
import logging

from hat import aio
from hat import chatter
from hat import util
from hat.event import common


mlog = logging.getLogger(__name__)

reconnect_delay = 0.5


async def connect(address, subscriptions=None, **kwargs):
    """Connect to event server

    For address format see :func:`hat.chatter.connect`.

    According to Event Server specification, each subscription is event
    type identifier which can contain special subtypes ``?`` and ``*``.
    Subtype ``?`` can occure at any position inside event type identifier
    and is used as replacement for any single subtype. Subtype ``*`` is valid
    only as last subtype in event type identifier and is used as replacement
    for zero or more arbitrary subtypes.

    If subscription is not defined (is None), client doesn't subscribe for any
    events and will not receive server's notifications.

    Args:
        address (str): event server's address
        subscriptions (Optional[List[common.EventType]]): subscriptions
        kwargs: additional arguments passed to :func:`hat.chatter.connect`

    Returns:
        Client

    """
    client = Client()
    client._async_group = aio.Group(exception_cb=client._on_exception_cb)
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


class Client:
    """Event Server client

    For creating new client see :func:`connect`.

    """

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    async def receive(self):
        """Receive subscribed event notifications

        Returns:
            List[common.Event]

        Raises:
            chatter.ConnectionClosedError: closed chatter connection

        """
        try:
            return await self._event_queue.get()
        except aio.QueueClosedError:
            raise chatter.ConnectionClosedError

    def register(self, events):
        """Register events

        Args:
            events (List[common.RegisterEvent]): register events

        Raises:
            chatter.ConnectionClosedError: closed chatter connection
            Exception

        """
        self._conn.send(chatter.Data(
            module='HatEvent',
            type='MsgRegisterReq',
            data=[common.register_event_to_sbs(i) for i in events]))

    async def register_with_response(self, events):
        """Register events

        Each `RegisterEvent` from `events` is paired with results `Event` if
        new event was successfuly created or `None` is new event could not
        be created.

        Args:
            events (List[common.RegisterEvent]): register events

        Returns:
            List[Optional[common.Event]]

        Raises:
            chatter.ConnectionClosedError: closed chatter connection
            Exception

        """
        conv = self._conn.send(chatter.Data(
            module='HatEvent',
            type='MsgRegisterReq',
            data=[common.register_event_to_sbs(i) for i in events]),
                               last=False)
        response_future = asyncio.Future()
        self._conv_futures[conv] = response_future
        return await response_future

    async def query(self, data):
        """Query events from server

        Args:
            data (common.QueryData): query data

        Returns:
            List[common.Event]

        Raises:
            chatter.ConnectionClosedError: closed chatter connection
            Exception

        """
        conv = self._conn.send(chatter.Data(
            module='HatEvent',
            type='MsgQueryReq',
            data=common.query_to_sbs(data)), last=False)
        response_future = asyncio.Future()
        self._conv_futures[conv] = response_future
        return await response_future

    async def _receive_loop(self):
        try:
            while True:
                msg = await self._conn.receive()
                self._process_received_msg(msg)
        except chatter.ConnectionClosedError:
            mlog.debug('connection closed')
        finally:
            self._async_group.close()
            self._event_queue.close()
            for f in self._conv_futures.values():
                f.set_exception(chatter.ConnectionClosedError)

    def _process_received_msg(self, msg):
        if msg.data.module != 'HatEvent':
            raise Exception('Message received from communication malformed!')
        if msg.data.type == 'MsgNotify':
            self._event_queue.put_nowait(
                [common.event_from_sbs(e) for e in msg.data.data])
            return
        if msg.conv not in self._conv_futures:
            return
        f = self._conv_futures.pop(msg.conv)
        if msg.data.type == 'MsgQueryRes':
            f.set_result([common.event_from_sbs(e) for e in msg.data.data])
        elif msg.data.type == 'MsgRegisterRes':
            f.set_result([{'event': common.event_from_sbs(e[1]),
                           'failure': None}[e[0]] for e in msg.data.data])
        else:
            raise Exception('Message received from communication malformed!')

    def _on_exception_cb(self, exc):
        mlog.error('exception in receive loop: %s', exc, exc_info=exc)


async def run_client(monitor_client, server_group, async_run_cb,
                     subscriptions=None):
    """Continuously communicate with currently active Event Server

    This function tries to establish active connection with Event Server.
    Once this connection is established, `async_run_cb` is called with
    currently active :class:`Client`. Once connection to Event Server is closed
    or new active Event Server is detected, execution of `async_run_cb` is
    canceled. If new connection to Event Server is successfuly established,
    `async_run_cb` is called with new instance of :class:`Client`.

    `async_run_cb` is called when:
        * new active :class:`Client` is created

    `async_run_cb` execution is cancelled when:
        * :func:`run_client` finishes execution
        * connection to Event Server is closed
        * different active Event Server is detected from Monitor Server's list
          of components

    :func:`run_client` finishes execution when:
        * connection to Monitor Server is closed
        * `async_run_cb` finishes execution (by returning value or raising
          exception other than asyncio.CancelledError)

    Return value of this function is the same as return value of
    `async_run_cb`. If `async_run_cb` finishes by raising exception or if
    connection to Monitor Server is closed, exception is reraised.

    .. todo::

        review conditions when `run_client` finishes execution

    Args:
        monitor_client (hat.monitor.client.Client): monitor client
        server_group (str): event server's component group
        async_run_cb (Callable[[Client],None]): run callback
        subscriptions (Optional[List[common.EventType]]): subscriptions

    Returns:
        Any

    """
    address = None
    address_change = asyncio.Event()

    async def _address_loop(monitor_client, address_change, server_group):
        nonlocal address
        queue = aio.Queue()
        with monitor_client.register_change_cb(lambda: queue.put_nowait(None)):
            while True:
                new_address = _get_server_address(monitor_client.components,
                                                  server_group)
                if new_address != address:
                    address = new_address
                    address_change.set()
                await queue.get()

    async with aio.Group() as group:
        group.spawn(_address_loop,
                    monitor_client, address_change, server_group)
        while True:
            address_change.clear()
            while not address:
                await address_change.wait()

            async with group.create_subgroup() as subgroup:
                connect_and_run_future = subgroup.spawn(
                    _connect_and_run_loop, subgroup, address,
                    subscriptions, async_run_cb)
                address_change.clear()
                wait_futures = [connect_and_run_future,
                                subgroup.spawn(address_change.wait),
                                monitor_client.closed]
                await asyncio.wait(wait_futures,
                                   return_when=asyncio.FIRST_COMPLETED)
                if monitor_client.closed.done():
                    raise Exception('connection to monitor server closed')
                elif connect_and_run_future.done():
                    return connect_and_run_future.result()


async def _connect_and_run_loop(group, address, subscriptions,
                                async_run_cb):
    while True:
        client = None
        while not client:
            try:
                client = await connect(address, subscriptions)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                mlog.warning('error on connecting to event server, '
                             'will try to reconnect... %s', e, exc_info=e)
                await asyncio.sleep(reconnect_delay)

        try:
            async with group.create_subgroup() as subgroup:
                run_future = subgroup.spawn(async_run_cb, client)
                await asyncio.wait([run_future, client.closed],
                                   return_when=asyncio.FIRST_COMPLETED)
                # TODO maybe we should check for closing.done()
                if client.closed.done():
                    mlog.warning('connection to event server closed')
                    continue
                elif run_future.done():
                    mlog.debug('async_run_cb finished or raised an exception')
                    try:
                        return run_future.result()
                    except asyncio.CancelledError:
                        continue
        finally:
            await client.async_close()


def _get_server_address(components, server_group):
    server_info = util.first(components, lambda c: (
        c.group == server_group and
        c.blessing is not None and
        c.blessing == c.ready))
    return server_info.address if server_info else None
