"""Juggler communication protocol

This module implements basic communication infrastructure used for
communication between back-end and GUI front-end parts of Hat components.

Example usage of Juggler communication::

    srv_conn = None

    def on_connection(conn):
        global srv_conn
        srv_conn = conn

    srv = await listen('127.0.0.1', 1234, on_connection)

    conn = await connect('ws://127.0.0.1:1234/ws')

    conn.set_local_data(123)

    await asyncio.sleep(0.3)

    assert srv_conn.remote_data == conn.local_data

    await conn.async_close()
    await srv.async_close()


Attributes:
    mlog (logging.Logger): module logger

"""

import aiohttp.web
import asyncio
import contextlib
import logging
import pathlib
import typing
import ssl

from hat import aio
from hat import json
from hat import util


mlog = logging.getLogger(__name__)


ConnectionCb = typing.Callable[['Connection'], None]


async def connect(address: str, *,
                  autoflush_delay: typing.Optional[float] = 0.2,
                  ) -> 'Connection':
    """Connect to remote server

    Address represents remote WebSocket URL formated as
    ``<schema>://<host>:<port>/<path>`` where ``<schema>`` is ``ws`` or
    ``wss``.

    Argument `autoflush_delay` defines maximum time delay for automatic
    synchronization of `local_data` changes. If `autoflush_delay` is set to
    ``None``, automatic synchronization is disabled and user is responsible
    for calling :meth:`Connection.flush_local_data`. If `autoflush_delay` is
    set to ``0``, synchronization of `local_data` is performed on each change
    of `local_data`.

    Args:
        address: remote server address
        autoflush_delay: autoflush delay

    """
    session = aiohttp.ClientSession()
    try:
        ws = await session.ws_connect(address, max_msg_size=0)
    except Exception:
        await session.close()
        raise
    conn = _create_connection(ws=ws,
                              autoflush_delay=autoflush_delay,
                              session=session)
    return conn


async def listen(host: str,
                 port: int,
                 connection_cb: ConnectionCb, *,
                 ws_path: str = '/ws',
                 static_dir: typing.Optional[pathlib.Path] = None,
                 index_path: typing.Optional[str] = '/index.html',
                 pem_file: typing.Optional[pathlib.Path] = None,
                 autoflush_delay: typing.Optional[float] = 0.2,
                 shutdown_timeout: float = 0.1
                 ) -> 'Server':
    """Create listening server

    Each time server receives new incomming juggler connection, `connection_cb`
    is called with newly created connection.

    If `static_dir` is set, server serves static files is addition to providing
    juggler communication.

    If `index_path` is set, request for url path ``/`` are redirected to
    `index_path`.

    If `pem_file` is set, server provides `https/wss` communication instead
    of `http/ws` communication.

    Argument `autoflush_delay` is associated with all connections associated
    with this server (see :func:`connect`).

    `shutdown_timeout` defines maximum time duration server will wait for
    regular connection close procedures during server shutdown. All connections
    that are not closed during this period are forcefully closed.

    Args:
        host: listening hostname
        port: listening TCP port
        connection_cb: connection callback
        ws_path: WebSocket url path segment
        static_dir: static files directory path
        index_path: index path
        pem_file: PEM file path
        autoflush_delay: autoflush delay
        shutdown_timeout: shutdown timeout

    """
    server = Server()
    server._connection_cb = connection_cb
    server._autoflush_delay = autoflush_delay
    server._async_group = aio.Group(exception_cb=_on_exception)

    routes = []

    if index_path:

        async def root_handler(request):
            raise aiohttp.web.HTTPFound(index_path)

        routes.append(aiohttp.web.get('/', root_handler))

    routes.append(aiohttp.web.get(ws_path, server._ws_handler))

    if static_dir:
        routes.append(aiohttp.web.static('/', static_dir))

    app = aiohttp.web.Application()
    app.add_routes(routes)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()

    ssl_ctx = _create_ssl_context(pem_file) if pem_file else None
    site = aiohttp.web.TCPSite(runner=runner,
                               host=host,
                               port=port,
                               shutdown_timeout=shutdown_timeout,
                               ssl_context=ssl_ctx,
                               reuse_address=True)
    await site.start()

    server._async_group.spawn(aio.call_on_cancel, runner.cleanup)
    return server


class Server:
    """Server

    For creating new server see :func:`listen`.

    """

    @property
    def closed(self) -> asyncio.Future:
        """Closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close server and all active connections"""
        await self._async_group.async_close()

    async def _ws_handler(self, request):
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        conn = _create_connection(ws=ws,
                                  autoflush_delay=self._autoflush_delay,
                                  parent_group=self._async_group)
        self._connection_cb(conn)
        await conn.closed
        return ws


def _create_connection(ws, autoflush_delay, session=None, parent_group=None):
    conn = Connection()
    conn._ws = ws
    conn._autoflush_delay = autoflush_delay
    conn._session = session
    conn._remote_change_cbs = util.CallbackRegistry()
    conn._remote_data = None
    conn._local_data = None
    conn._message_queue = aio.Queue()
    conn._flush_queue = aio.Queue()
    conn._local_data_queue = aio.Queue()
    conn._async_group = (parent_group.create_subgroup() if parent_group else
                         aio.Group(exception_cb=_on_exception))

    conn._async_group.spawn(aio.call_on_cancel, conn._on_close)
    conn._async_group.spawn(conn._receive_loop)
    conn._async_group.spawn(conn._sync_loop)

    return conn


class Connection:
    """Connection

    For creating new connection see :func:`connect`.

    """

    @property
    def closed(self) -> asyncio.Future:
        """Closed future"""
        return self._async_group.closed

    @property
    def local_data(self) -> json.Data:
        """Local data"""
        return self._local_data

    @property
    def remote_data(self) -> json.Data:
        """remote data"""
        return self._remote_data

    def register_change_cb(self, cb: typing.Callable[[], None]
                           ) -> util.RegisterCallbackHandle:
        """Register remote data change callback"""
        return self._remote_change_cbs.register(cb)

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    def set_local_data(self, data: json.Data):
        """Set local data

        Raises:
            ConnectionError

        """
        try:
            self._local_data_queue.put_nowait(data)
            self._local_data = data
        except aio.QueueClosedError:
            raise ConnectionError()

    async def flush_local_data(self):
        """Force synchronization of local data

        Raises:
            ConnectionError

        """
        try:
            flush_future = asyncio.Future()
            self._flush_queue.put_nowait(flush_future)
            await flush_future
        except aio.QueueClosedError:
            raise ConnectionError()

    async def send(self, msg: json.Data):
        """Send message

        Raises:
            ConnectionError

        """
        if self._async_group.closing.done():
            raise ConnectionError()

        await self._ws.send_json({'type': 'MESSAGE', 'payload': msg})

    async def receive(self) -> json.Data:
        """Receive message

        Raises:
            ConnectionError

        """
        try:
            return await self._message_queue.get()
        except aio.QueueClosedError:
            raise ConnectionError()

    async def _on_close(self):
        self._message_queue.close()
        self._flush_queue.close()
        self._local_data_queue.close()

        while not self._flush_queue.empty():
            f = self._flush_queue.get_nowait()
            if not f.done():
                f.set_exception(ConnectionError())

        with contextlib.suppress(Exception, asyncio.CancelledError):
            await self._ws.close()
        if self._session:
            await self._session.close()

    async def _receive_loop(self):
        try:
            while True:
                msg_ws = await self._ws.receive()
                if self._ws.closed or msg_ws.type == aiohttp.WSMsgType.CLOSING:
                    break
                if msg_ws.type != aiohttp.WSMsgType.TEXT:
                    raise Exception('unsupported message type')

                msg = json.decode(msg_ws.data)

                if msg['type'] == 'MESSAGE':
                    self._message_queue.put_nowait(msg['payload'])

                elif msg['type'] == 'DATA':
                    self._remote_data = json.patch(self._remote_data,
                                                   msg['payload'])
                    self._remote_change_cbs.notify()

                else:
                    raise Exception("invalid message type")

        finally:
            self._async_group.close()

    async def _sync_loop(self):
        data = None
        synced_data = None
        flush_future = None

        try:
            get_data_future = self._async_group.spawn(
                self._local_data_queue.get)
            get_flush_future = self._async_group.spawn(
                self._flush_queue.get)

            while True:

                await asyncio.wait([get_data_future, get_flush_future],
                                   return_when=asyncio.FIRST_COMPLETED)

                if get_flush_future.done():
                    flush_future = get_flush_future.result()
                    get_flush_future = self._async_group.spawn(
                        self._flush_queue.get)

                else:
                    await asyncio.wait([get_flush_future],
                                       timeout=self._autoflush_delay)

                    if get_flush_future.done():
                        flush_future = get_flush_future.result()
                        get_flush_future = self._async_group.spawn(
                            self._flush_queue.get)
                    else:
                        flush_future = None

                if get_data_future.done():
                    data = get_data_future.result()
                    get_data_future = self._async_group.spawn(
                        self._local_data_queue.get)

                if self._autoflush_delay != 0:
                    if not self._local_data_queue.empty():
                        data = self._local_data_queue.get_nowait_until_empty()

                if synced_data is not data:
                    diff = json.diff(synced_data, data)
                    synced_data = data
                    if diff:
                        await self._ws.send_json({'type': 'DATA',
                                                  'payload': diff})

                if flush_future and not flush_future.done():
                    flush_future.set_result(True)

        finally:
            self._async_group.close()


def _on_exception(exc):
    if isinstance(exc, aio.QueueClosedError):
        return
    mlog.error("juggler connection error: %s", exc, exc_info=exc)


def _create_ssl_context(pem_file):
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
    ssl_ctx.verify_mode = ssl.VerifyMode.CERT_NONE
    if pem_file:
        ssl_ctx.load_cert_chain(str(pem_file))
    return ssl_ctx
