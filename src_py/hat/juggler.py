"""Juggler communication protocol

This module implements basic communication infrastructure used for
communication between back-end and GUI front-end parts of Hat components.

"""

import aiohttp.web
import asyncio
import logging
import pathlib
import ssl
import typing

from hat import aio
from hat import json
from hat import util


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

ConnectionCb = typing.Callable[['Connection'], None]
"""Connection callback"""


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

    except BaseException:
        await aio.uncancellable(session.close())
        raise

    return _create_connection(aio.Group(), ws, autoflush_delay, session)


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
    with this server (see `connect`).

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
    async_group = aio.Group()

    server = Server()
    server._connection_cb = connection_cb
    server._autoflush_delay = autoflush_delay
    server._async_group = async_group

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
    async_group.spawn(aio.call_on_cancel, runner.cleanup)

    try:
        ssl_ctx = _create_ssl_context(pem_file) if pem_file else None
        site = aiohttp.web.TCPSite(runner=runner,
                                   host=host,
                                   port=port,
                                   shutdown_timeout=shutdown_timeout,
                                   ssl_context=ssl_ctx,
                                   reuse_address=True)
        await site.start()

    except BaseException:
        await aio.uncancellable(async_group.async_close())
        raise

    return server


class Server(aio.Resource):
    """Server

    For creating new server see `listen` coroutine.

    When server is closed, all incomming connections are also closed.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def _ws_handler(self, request):
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        subgroup = self._async_group.create_subgroup()
        conn = _create_connection(subgroup, ws, self._autoflush_delay)
        self._connection_cb(conn)
        await conn.wait_closed()
        return ws


def _create_connection(async_group, ws, autoflush_delay, session=None):
    conn = Connection()
    conn._async_group = async_group
    conn._ws = ws
    conn._autoflush_delay = autoflush_delay
    conn._session = session
    conn._remote_change_cbs = util.CallbackRegistry()
    conn._remote_data = None
    conn._local_data = None
    conn._message_queue = aio.Queue()
    conn._flush_queue = aio.Queue()
    conn._local_data_queue = aio.Queue()

    async_group.spawn(aio.call_on_cancel, conn._on_close)
    async_group.spawn(conn._receive_loop)
    async_group.spawn(conn._sync_loop)

    return conn


class Connection(aio.Resource):
    """Connection

    For creating new connection see `connect` coroutine.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def local_data(self) -> json.Data:
        """Local data"""
        return self._local_data

    @property
    def remote_data(self) -> json.Data:
        """Remote data"""
        return self._remote_data

    def register_change_cb(self,
                           cb: typing.Callable[[], None]
                           ) -> util.RegisterCallbackHandle:
        """Register remote data change callback"""
        return self._remote_change_cbs.register(cb)

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
        if self._async_group.is_closing:
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

        await self._ws.close()
        if not self._session:
            return
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

        except Exception as e:
            mlog.error("juggler receive loop error: %s", e, exc_info=e)

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

        except aio.QueueClosedError:
            pass

        except Exception as e:
            mlog.error("juggler sync loop error: %s", e, exc_info=e)

        finally:
            self._async_group.close()


def _create_ssl_context(pem_file):
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
    ssl_ctx.verify_mode = ssl.VerifyMode.CERT_NONE
    if pem_file:
        ssl_ctx.load_cert_chain(str(pem_file))
    return ssl_ctx
