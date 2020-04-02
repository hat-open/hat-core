"""Juggler communication protocol

This module implements basic communication infrastructure used for
communication between back-end and GUI front-end parts of Hat components.

Attributes:
    mlog (logging.Logger): module logger
    sync_local_delay (float): delay on syncing local data changes in seconds
    server_connects_close_timeout (float): timeout for closing opened
        connections
"""

import aiohttp.web
import asyncio
import contextlib
import logging
import urllib

from hat import util
from hat.util import aio
from hat.util import json


mlog = logging.getLogger(__name__)

sync_local_delay = 0.2

server_connects_close_timeout = 0.1


class ConnectionClosedError(Exception):
    """Error signaling closed connection"""


async def connect(address):
    """Connect to remote server

    Address represents remote WebSocket URL formated as
    ``ws://<host>:<port>/<path>``.

    .. todo::

        add wss support

    Args:
        address (str): remote server address

    Returns:
        Connection

    """
    session = aiohttp.ClientSession()
    try:
        ws = await session.ws_connect(address)
    except Exception:
        await session.close()
        raise
    conn = _create_connection(ws, session=session)
    return conn


async def listen(address, connection_cb, *, static_path=None):
    """Create listening server

    For address formating see :func:`connect`.

    .. todo::

        * review address format for listen
        * add https support

    Args:
        address (str): listening address
        connection_cb (Callable[[Connection],None]): new connection callback
        static_path (Optional[os.PathLike]): static directory path

    Returns:
        Server

    """

    async def root_handler(request):
        raise aiohttp.web.HTTPFound('/index.html')

    server = Server()
    server._async_group = aio.Group()
    server._connection_cb = connection_cb

    app = aiohttp.web.Application()
    address = urllib.parse.urlparse(address)
    routes = [aiohttp.web.get('/', root_handler),
              aiohttp.web.get(address.path, server._ws_handler)]
    if static_path:
        routes.append(aiohttp.web.static('/', static_path))
    app.add_routes(routes)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner,
                               host=address.hostname, port=address.port,
                               shutdown_timeout=server_connects_close_timeout,
                               reuse_address=True)
    await site.start()
    server._async_group.spawn(aio.call_on_cancel, runner.cleanup)
    return server


class Server:
    """Server

    For creating new server see :func:`listen`.

    """

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close server and all active connections"""
        await self._async_group.async_close()

    async def _ws_handler(self, request):
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        conn = _create_connection(ws, parent_group=self._async_group)
        self._connection_cb(conn)
        await conn.closed
        return ws


def _create_connection(ws, parent_group=None, session=None):
    conn = Connection()
    conn._local_data_synced = None
    conn._remote_data = None
    conn._local_data = None
    conn._sync_local_future = None
    conn._flush_future = asyncio.Future()
    conn._flush_future.set_result(None)
    conn._message_queue = aio.Queue()
    conn._remote_change_cbs = util.CallbackRegistry()
    conn._async_group = (parent_group.create_subgroup() if parent_group else
                         aio.Group(exception_cb=conn._on_exception))
    conn._ws = ws
    conn._session = session
    conn._async_group.spawn(conn._receive_loop)
    return conn


class Connection:
    """Connection

    For creating new connection see :func:`connect`.

    """

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    @property
    def local_data(self):
        """json.Data: local data"""
        return self._local_data

    @property
    def remote_data(self):
        """json.Data: remote data"""
        return self._remote_data

    def register_change_cb(self, cb):
        """Register remote data change callback

        Args:
            cb (Callable[[],None]): change callback

        Returns:
            util.RegisterCallbackHandle

        """
        return self._remote_change_cbs.register(cb)

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    def set_local_data(self, data):
        """Set local data

        Args:
            data (json.Data): local data

        Raises:
            ConnectionClosedError

        """
        if self._async_group.closed.done():
            raise ConnectionClosedError()
        self._local_data = data
        if self._flush_future.done():
            self._flush_future = asyncio.Future()
            self._sync_local_future = self._async_group.spawn(
                self._sync_local_delayed)

    async def flush_local_data(self):
        """Force synchronization of local data

        Raises:
            ConnectionClosedError

        """
        if self._async_group.closed.done():
            raise ConnectionClosedError()
        if not self._flush_future.done():
            self._flush_future.set_result(None)
            await asyncio.shield(self._sync_local_future)

    async def send(self, msg):
        """Send message

        Args:
            msg (json.Data): message

        Raises:
            ConnectionClosedError

        """
        if self._async_group.closed.done():
            raise ConnectionClosedError()
        await self._ws.send_json({'type': 'MESSAGE', 'payload': msg})

    async def receive(self):
        """Receive message

        Returns:
            json.Data: message

        Raises:
            ConnectionClosedError

        """
        try:
            return await self._message_queue.get()
        except aio.QueueClosedError:
            raise ConnectionClosedError()

    async def _sync_local_delayed(self):
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._flush_future, sync_local_delay)
        await self._sync_local()

    async def _sync_local(self):
        if self._async_group.closed.done():
            raise ConnectionClosedError()
        diff = json.diff(self._local_data_synced, self._local_data)
        if not diff:
            return
        self._local_data_synced = self._local_data
        await self._ws.send_json({'type': 'DATA', 'payload': diff})

    async def _receive_loop(self):
        try:
            while True:
                msg_ws = await self._ws.receive()
                if self._ws.closed or msg_ws.type == aiohttp.WSMsgType.CLOSING:
                    break
                if msg_ws.type != aiohttp.WSMsgType.TEXT:
                    raise Exception('unsupported message type')
                msg = json.decode(msg_ws.data)
                process_payload = {
                    'DATA': self._process_juggler_data,
                    'MESSAGE': self._process_juggler_message}.get(msg['type'])
                process_payload(msg['payload'])
        finally:
            self._async_group.close()
            await aio.uncancellable(self._ws.close(), raise_cancel=False)
            if self._session:
                await self._session.close()
            self._message_queue.close()

    def _process_juggler_data(self, diff):
        self._remote_data = json.patch(self._remote_data, diff)
        self._remote_change_cbs.notify()

    def _process_juggler_message(self, message):
        self._message_queue.put_nowait(message)

    def _on_exception(self, exc):
        mlog.error("error in a Connection's loop: %s", exc, exc_info=exc)
