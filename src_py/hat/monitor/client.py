"""Library used by components for communication with Monitor Server

This module provides low-level interface (`connect`/`Client`) and high-level
interface (`run_component`) for communication with Monitor Server.

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

`run_component` provide high-level interface for communication with
Monitor Server. This function first establishes connection to Monitor
Server and then listens component changes and in regard to blessing
and ready tokens calls or cancels `async_run_cb` callback.
In case blessing token matches ready token, `async_run_cb` is called.
While `async_run_cb` is running, once blessing token changes, `async_run_cb` is
canceled. If `async_run_cb` finishes or raises exception, this function closes
connection to monitor server and returns `async_run_cb` result. If connection
to monitor server is closed, this function raises exception.

Example of high-level interface usage::

    async def monitor_async_run():
        await asyncio.sleep(10)
        return 13

    client = await hat.monitor.client.connect({
        'name': 'client',
        'group': 'test clients',
        'monitor_address': 'tcp+sbs://127.0.0.1:23010',
        'component_address': None})
    res = await hat.monitor.client.run_component(client, monitor_async_run)
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


T = typing.TypeVar('T')


async def run_component(client: Client,
                        async_run_cb: typing.Callable[..., typing.Awaitable[T]],  # NOQA
                        *args, **kwargs
                        ) -> T:
    """Run component

    This starts client's loop which manages blessing/ready states based on
    provided monitor client. This implementation sets ready token immediately
    after blessing token is detected.

    When blessing token matches ready token, `async_run_cb` is called with
    additional `args` and `kwargs` arguments. While `async_run_cb` is running,
    if blessing token changes, `async_run_cb` is canceled.

    If `async_run_cb` finishes or raises exception, this function returns
    `async_run_cb` result. If connection to monitor server is closed, this
    function raises `ConnectionError`.

    """
    change_queue = aio.Queue()
    async_group = aio.Group()

    def on_client_change():
        change_queue.put_nowait(None)

    closing_future = async_group.spawn(client.wait_closing)
    change_handler = client.register_change_cb(on_client_change)
    async_group.spawn(aio.call_on_cancel, change_handler.cancel)

    async def wait_until_blessed_and_ready():
        while True:
            blessing = client.info.blessing if client.info else None
            ready = client.info.ready if client.info else None

            client.set_ready(blessing)
            if blessing is not None and blessing == ready:
                break

            await change_queue.get_until_empty()

    async def wait_while_blessed_and_ready():
        while True:
            blessing = client.info.blessing if client.info else None
            ready = client.info.ready if client.info else None

            if blessing is None or blessing != ready:
                client.set_ready(None)
                break

            await change_queue.get_until_empty()

    try:
        while True:
            async with async_group.create_subgroup() as subgroup:
                mlog.debug("waiting blessing and ready")

                ready_future = subgroup.spawn(wait_until_blessed_and_ready)

                await asyncio.wait([ready_future,
                                    closing_future],
                                   return_when=asyncio.FIRST_COMPLETED)

                if closing_future.done():
                    raise ConnectionError()

            async with async_group.create_subgroup() as subgroup:
                mlog.debug("running component's async_run_cb")

                run_future = subgroup.spawn(async_run_cb, *args, **kwargs)
                ready_future = subgroup.spawn(wait_while_blessed_and_ready)

                await asyncio.wait([run_future,
                                    ready_future,
                                    closing_future],
                                   return_when=asyncio.FIRST_COMPLETED)

                if run_future.done():
                    return run_future.result()

                if closing_future.done():
                    raise ConnectionError()

    except ConnectionError:
        raise

    except Exception as e:
        mlog.warning("run component error: %s", e, exc_info=e)
        raise

    finally:
        await aio.uncancellable(async_group.async_close())
        mlog.debug("component closed")
