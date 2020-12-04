"""Library used by components for communication with Monitor Server

This module provides low-level interface (connect/Client) and high-level
interface (run_component) for communication with Monitor Server.


:func:`connect` is used for establishing single chatter based connection
with Monitor Server which is represented by :class:`Client`. Termination of
connection is signaled with :meth:`Client.closed`.

Example of low-level interface usage::

    client = await hat.monitor.client.connect({
        'name': 'client1',
        'group': 'group1',
        'monitor_address': 'tcp+sbs://127.0.0.1:23010',
        'component_address': None})
    assert client.info in client.components
    try:
        await client.closed
    finally:
        await client.async_close()

:func:`run_component` provide high-level interface for communication with
Monitor Server. This function first establishes connection to Monitor
Server and then listens component changes and in regard to blessing
and ready tokens calls or cancels `async_run_cb` callback.
In case blessing token matches ready token, `async_run_cb` is called.
While `async_run_cb` is running, once blessing token changes, `async_run_cb` is
canceled. If `async_run_cb` finishes or raises exception, this function closes
connection to monitor server and returns `async_run_cb` result. If connection
to monitor server is closed, this function raises exception.

Example of high-level interface usage::

    async def monitor_async_run(monitor):
        await asyncio.sleep(10)
        return 13

    res = await hat.monitor.client.run_component(
        conf={'name': 'client',
              'group': 'test clients',
              'monitor_address': 'tcp+sbs://127.0.0.1:23010',
              'component_address': None},
        async_run_cb=monitor_async_run)
    assert res == 13

Attributes:
    mlog (logging.Logger): module logger

"""

import asyncio
import logging

from hat import aio
from hat import chatter
from hat import util
from hat.monitor import common


mlog = logging.getLogger(__name__)


async def connect(conf):
    """Connect to local monitor server

    Connection is established once chatter communication is established.

    Args:
        conf (hat.json.Data): configuration as defined by
            ``hat://monitor/client.yaml#``

    Returns:
        Client

    """
    client = Client()
    client._name = conf['name']
    client._group = conf['group']
    client._address = conf['component_address']
    client._components = []
    client._info = None
    client._ready = None
    client._change_cbs = util.CallbackRegistry()
    client._async_group = aio.Group()

    client._conn = await chatter.connect(common.sbs_repo,
                                         conf['monitor_address'])
    client._async_group.spawn(aio.call_on_cancel, client._conn.async_close)
    mlog.debug("connected to local monitor server %s", conf['monitor_address'])
    client._async_group.spawn(client._receive_loop)
    return client


class Client:

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    @property
    def info(self):
        """Optional[common.ComponentInfo]: client's component info"""
        return self._info

    @property
    def components(self):
        """List[common.ComponentInfo]: global component state"""
        return self._components

    def register_change_cb(self, cb):
        """Register change callback

        Registered callback is called once info and/or components changes.

        Args:
            cb (Callable[[],None]): callback

        Returns:
            util.RegisterCallbackHandle

        """
        return self._change_cbs.register(cb)

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    def set_ready(self, token):
        """Set ready token

        Args:
            token (Optional[int]): ready token

        """
        if token == self._ready:
            return
        self._ready = token
        self._send_msg_client()

    def _send_msg_client(self):
        self._conn.send(chatter.Data(
            module='HatMonitor',
            type='MsgClient',
            data=common.create_msg_client_sbs(
                name=self._name,
                group=self._group,
                address=self._address,
                ready=self._ready)))

    def _set_components(self, msg_server):
        if (msg_server.data.module != 'HatMonitor' or
                msg_server.data.type != 'MsgServer'):
            raise Exception('Message received from server malformed: message '
                            'MsgServer from HatMonitor module expected')
        self._components = [common.component_info_from_sbs(i)
                            for i in msg_server.data.data['components']]
        self._info = util.first(
            self._components,
            lambda i:
                i.cid == msg_server.data.data['cid'] and
                i.mid == msg_server.data.data['mid'])
        self._change_cbs.notify()

    async def _receive_loop(self):
        try:
            self._send_msg_client()
            while True:
                msg = await self._conn.receive()
                self._set_components(msg)
        except chatter.ConnectionClosedError:
            mlog.debug('connection closed')
        finally:
            self._async_group.close()


async def run_component(conf, async_run_cb):
    """Run component

    This method opens new connection to Monitor server and starts client's
    loop which manages blessing/ready states.

    When blessing token matches ready token, `async_run_cb` is called. While
    `async_run_cb` is running, if blessing token changes, `async_run_cb` is
    canceled.

    If `async_run_cb` finishes or raises exception, this function closes
    connection to monitor server and returns `async_run_cb` result. If
    connection to monitor server is closed, this function raises exception.

    TODO:
        * provide opportunity for user to react to blessing token prior to
          setting ready token (additional async_ready_cb)

    Args:
        conf (hat.json.Data): configuration as defined by
            ``hat://monitor/client.yaml#``
        async_run_cb (Callable[[Client],None]): run callback

    Returns:
        Any

    """
    client = await connect(conf)
    try:
        while True:
            await _wait_until_blessed_and_ready(client)
            async_group = aio.Group()
            run_future = async_group.spawn(async_run_cb, client)
            blessed_and_ready_future = async_group.spawn(
                _wait_while_blessed_and_ready, client)
            try:
                done, _ = await asyncio.wait(
                    [run_future, blessed_and_ready_future, client.closed],
                    return_when=asyncio.FIRST_COMPLETED)
                if run_future.done():
                    mlog.debug('async_run_cb finished or raised an exception')
                    return run_future.result()
                if client.closed.done():
                    raise Exception('connection to monitor server closed!')
            finally:
                if not client.closed.done():
                    client.set_ready(None)
                await async_group.async_close()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        mlog.error('run component exception: %s', e, exc_info=e)
        raise
    finally:
        await client.async_close()
        mlog.debug('component closed')


async def _wait_until_blessed_and_ready(client):
    queue = aio.Queue()
    with client.register_change_cb(lambda: queue.put_nowait(None)):
        while (client.info is None or client.info.blessing is None or
               client.info.blessing != client.info.ready):
            await queue.get_until_empty()
            if client.info is None:
                continue
            client.set_ready(client.info.blessing)


async def _wait_while_blessed_and_ready(client):
    queue = aio.Queue()
    with client.register_change_cb(lambda: queue.put_nowait(None)):
        while (client.info is not None and
               client.info.blessing is not None and
               client.info.blessing == client.info.ready):
            await queue.get_until_empty()
