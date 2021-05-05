"""Library used by components for communication with Monitor Server

This module provides low-level interface (`connect`/`Client`) and high-level
interface (`Component`) for communication with Monitor Server.

`connect` is used for establishing single chatter based connection
with Monitor Server which is represented by `Client`. Termination of
connection is signaled with `Client.wait_closed`.

Example of low-level interface usage::

    client = await hat.monitor.client.connect({
        'name': 'client1',
        'group': 'group1',
        'monitor_address': 'tcp+sbs://127.0.0.1:23010',
        'component_address': None})
    assert client.info in client.components
    try:
        await client.wait_closed()
    finally:
        await client.async_close()

`Component` provide high-level interface for communication with
Monitor Server. Component, listens to client changes and in regard to blessing
and ready tokens calls or cancels `async_run_cb` callback. In case component is
enabled and blessing token matches ready token, `async_run_cb` is called.
While `async_run_cb` is running, once enable state or blessing token changes,
`async_run_cb` is canceled. If `async_run_cb` finishes or raises exception or
connection to monitor server is closed, component is closed.

Example of high-level interface usage::

    async def monitor_async_run(_, f):
        await asyncio.sleep(10)
        f.set_result(13)

    client = await hat.monitor.client.connect({
        'name': 'client',
        'group': 'test clients',
        'monitor_address': 'tcp+sbs://127.0.0.1:23010',
        'component_address': None})
    f = asyncio.Future()
    component = Component(client, monitor_async_run, f)
    component.set_enabled(True)
    res = await f
    assert res == 13

"""

import asyncio
import logging
import typing

from hat import aio
from hat import chatter
from hat import json
from hat import util
from hat.monitor import common


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


async def connect(conf: json.Data
                  ) -> 'Client':
    """Connect to local monitor server

    Connection is established once chatter communication is established.

    Args:
        conf: configuration as defined by ``hat://monitor/client.yaml#``

    """
    client = Client()
    client._conf = conf
    client._components = []
    client._info = None
    client._ready = None
    client._change_cbs = util.CallbackRegistry()
    client._async_group = aio.Group()

    client._conn = await chatter.connect(common.sbs_repo,
                                         conf['monitor_address'])
    client._async_group.spawn(aio.call_on_cancel, client._conn.async_close)
    client._async_group.spawn(client._receive_loop)

    mlog.debug("connected to local monitor server %s", conf['monitor_address'])
    return client


class Client(aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def info(self) -> typing.Optional[common.ComponentInfo]:
        """Client's component info"""
        return self._info

    @property
    def components(self) -> typing.List[common.ComponentInfo]:
        """Global component state"""
        return self._components

    def register_change_cb(self,
                           cb: typing.Callable[[], None]
                           ) -> util.RegisterCallbackHandle:
        """Register change callback

        Registered callback is called once info and/or components changes.

        """
        return self._change_cbs.register(cb)

    def set_ready(self, token: typing.Optional[int]):
        """Set ready token"""
        if token == self._ready:
            return

        self._ready = token
        self._send_msg_client()

    async def _receive_loop(self):
        try:
            self._send_msg_client()

            while True:
                msg = await self._conn.receive()
                msg_type = msg.data.module, msg.data.type

                if msg_type == ('HatMonitor', 'MsgServer'):
                    msg_server = common.msg_server_from_sbs(msg.data.data)
                    self._process_msg_server(msg_server)

                else:
                    raise Exception('unsupported message type')

        except ConnectionError:
            mlog.debug("connection closed")

        except Exception as e:
            mlog.warning("monitor client error: %s", e, exc_info=e)

        finally:
            self._async_group.close()

    def _send_msg_client(self):
        msg_client = common.MsgClient(name=self._conf['name'],
                                      group=self._conf['group'],
                                      address=self._conf['component_address'],
                                      ready=self._ready)
        self._conn.send(chatter.Data(
            module='HatMonitor',
            type='MsgClient',
            data=common.msg_client_to_sbs(msg_client)))

    def _process_msg_server(self, msg_server):
        components = msg_server.components
        info = util.first(components, lambda i: (i.cid == msg_server.cid and
                                                 i.mid == msg_server.mid))

        if (self._components == components and self._info == info):
            return

        self._components = components
        self._info = info
        self._change_cbs.notify()


class Component(aio.Resource):
    """Monitor component

    Implementation of component behaviour according to BLESS_ALL and BLESS_ONE
    algorithms.

    Component runs client's loop which manages blessing/ready states based on
    provided monitor client and component's enabled state.

    When component is enabled and blessing token matches ready token,
    `async_run_cb` is called with component instance and additional `args` and
    `kwargs` arguments. While `async_run_cb` is running, if enabled state or
    blessing token changes, `async_run_cb` is canceled.

    If `async_run_cb` finishes or raises exception, component is closed.

    """

    def __init__(self,
                 client: Client,
                 async_run_cb: typing.Callable[..., typing.Awaitable],
                 *args, **kwargs):
        self._client = client
        self._async_run_cb = async_run_cb
        self._args = args
        self._kwargs = kwargs
        self._enabled = False
        self._change_queue = aio.Queue()
        self._async_group = client.async_group.create_subgroup()
        self._async_group.spawn(self._component_loop)

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def client(self) -> Client:
        """Client"""
        return self._client

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool):
        if self._enabled == enabled:
            return

        self._enabled = enabled
        self._change_queue.put_nowait(None)

    def _on_client_change(self):
        self._change_queue.put_nowait(None)

    async def _component_loop(self):
        try:
            with self._client.register_change_cb(self._on_client_change):
                while True:
                    mlog.debug("waiting blessing and ready")
                    await self._wait_until_blessed_and_ready()

                    async with self._async_group.create_subgroup() as subgroup:
                        mlog.debug("running component's async_run_cb")

                        run_future = subgroup.spawn(
                            self._async_run_cb, self, *self._args,
                            **self._kwargs)
                        ready_future = subgroup.spawn(
                            self._wait_while_blessed_and_ready)

                        await asyncio.wait([run_future, ready_future],
                                           return_when=asyncio.FIRST_COMPLETED)

                        if run_future.done():
                            return

        except ConnectionError:
            raise

        except Exception as e:
            mlog.warning("component loop error: %s", e, exc_info=e)

        finally:
            self.close()

    async def _wait_until_blessed_and_ready(self):
        while True:
            if self._enabled:
                info = self._client.info
                blessing = info.blessing if info else None
                ready = info.ready if info else None

                self._client.set_ready(blessing)
                if blessing and blessing == ready:
                    break

            else:
                self._client.set_ready(0)

            await self._change_queue.get_until_empty()

    async def _wait_while_blessed_and_ready(self):
        while True:
            if self._enabled:
                info = self._client.info
                blessing = info.blessing if info else None
                ready = info.ready if info else None

                if not blessing or blessing != ready:
                    self._client.set_ready(None)
                    break

            else:
                self._client.set_ready(0)
                break

            await self._change_queue.get_until_empty()
