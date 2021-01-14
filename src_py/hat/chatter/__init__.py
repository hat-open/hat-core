"""Chatter communication protocol

This module implements basic communication infrastructure used for Hat
communication. Hat communication is based on multiple loosely coupled services.
To implement communication with other Hat components, user should always
implement independent communication service (or use one of predefined
services).

"""

from pathlib import Path
import asyncio
import contextlib
import logging
import math
import ssl
import typing
import urllib.parse

from hat import aio
from hat import sbs


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


sbs_repo: sbs.Repository = sbs.Repository.from_json(Path(__file__).parent /
                                                    'sbs_repo.json')
"""Chatter message definition SBS repository"""


class Data(typing.NamedTuple):
    module: typing.Optional[str]
    """SBS module name"""
    type: str
    """SBS type name"""
    data: sbs.Data


class Conversation(typing.NamedTuple):
    conn: 'Connection'
    owner: bool
    first_id: int


class Msg(typing.NamedTuple):
    conn: 'Connection'
    data: Data
    conv: Conversation
    first: bool
    last: bool
    token: bool


class ConnectionClosedError(ConnectionError):
    """Error signaling closed connection"""


async def connect(sbs_repo: sbs.Repository,
                  address: str,
                  *,
                  pem_file: typing.Optional[str] = None,
                  ping_timeout: float = 20,
                  connect_timeout: float = 5,
                  queue_maxsize: int = 0
                  ) -> 'Connection':
    """Connect to remote server

    `sbs_repo` should include `hat.chatter.sbs_repo` and aditional message data
    definitions.

    Address is string formatted as `<scheme>://<host>:<port>` where

        * `<scheme>` - one of `tcp+sbs`, `ssl+sbs`
        * `<host>` - remote host's name
        * `<port>` - remote tcp port.

    PEM file is used only for ssl connection. If PEM file is not defined,
    certificate's authenticity is not established.

    If `ping_timeout` is ``None`` or 0, ping service is not registered,
    otherwise it represents ping timeout in seconds.

    `connect_timeout` represents connect timeout in seconds.

    `queue_maxsize` represents receive message queue maximum size. If set to
    ``0``, queue size is unlimited.

    Raises:
        OSError: could not connect to specified address
        ValueError: wrong address format
        socket.gaierror: unknown host name
        asyncio.TimeoutError: connect timeout

    """
    url = urllib.parse.urlparse(address)
    if not url.port:
        raise ValueError("Undefined port")
    if url.scheme == 'tcp+sbs':
        ssl_ctx = None
    elif url.scheme == 'ssl+sbs':
        ssl_ctx = _create_ssl_context(pem_file)
    else:
        raise ValueError("Undefined protocol")

    reader, writer = await asyncio.wait_for(asyncio.open_connection(
        url.hostname, url.port, ssl=ssl_ctx), connect_timeout)
    transport = _TcpTransport(sbs_repo, reader, writer)

    mlog.debug('client connection established')
    conn = _create_connection(sbs_repo, transport, ping_timeout, queue_maxsize)
    return conn


async def listen(sbs_repo: sbs.Repository,
                 address: str,
                 on_connection_cb: typing.Callable[['Connection'], None],
                 *,
                 pem_file: typing.Optional[str] = None,
                 ping_timeout: float = 20,
                 queue_maxsize: int = 0
                 ) -> 'Server':
    """Create listening server.

    `sbs_repo` is same as for :meth:`connect`.

    Address is same as for :meth:`connect`.

    If ssl connection is used, pem_file is required.

    `ping_timeout` is same as for :meth:`connect`.

    `queue_maxsize` is same as for :meth:`connect`.

    Raises:
        OSError: could not listen on specified address
        ValueError: wrong address format
        socket.gaierror: unknown host name

    """
    url = urllib.parse.urlparse(address)
    if url.port is None:
        raise ValueError("Undefined port")
    if url.scheme == 'tcp+sbs':
        ssl_ctx = None
    elif url.scheme == 'ssl+sbs':
        ssl_ctx = _create_ssl_context(pem_file)
    else:
        raise ValueError("Undefined protocol")

    async_group = aio.Group(_async_group_exception_cb)

    def connected_cb(reader, writer):
        mlog.debug("server accepted new connection")
        transport = _TcpTransport(sbs_repo, reader, writer)
        conn = _create_connection(sbs_repo, transport, ping_timeout,
                                  queue_maxsize, async_group)
        on_connection_cb(conn)

    srv = await asyncio.start_server(
        connected_cb, url.hostname, url.port, ssl=ssl_ctx)
    addresses = [
        _convert_sock_info_to_address(socket.getsockname(), url.scheme)
        for socket in srv.sockets]
    mlog.debug("listening socket created")

    async def on_close():
        srv.close()
        await srv.wait_closed()

    server = Server()
    server._addresses = addresses
    server._async_group = async_group
    server._async_group.spawn(aio.call_on_cancel, on_close)
    return server


class Server(aio.Resource):
    """Server

    For creating new server see :func:`listen`.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def addresses(self) -> typing.List[str]:
        """Listening addresses"""
        return self._addresses


def _create_connection(sbs_repo, transport, ping_timeout, queue_maxsize,
                       parent_async_group=None):
    conn = Connection()
    conn._sbs_repo = sbs_repo
    conn._transport = transport
    conn._last_id = 0
    conn._conv_timeouts = {}
    conn._msg_queue = aio.Queue(maxsize=queue_maxsize)
    conn._async_group = (parent_async_group.create_subgroup()
                         if parent_async_group is not None
                         else aio.Group(_async_group_exception_cb))
    conn._async_group.spawn(conn._read_loop)
    conn._async_group.spawn(conn._ping_loop, ping_timeout)
    return conn


class Connection(aio.Resource):
    """Single connection

    For creating new connection see :func:`connect`.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def local_address(self) -> str:
        """Local address"""
        return self._transport.local_address

    @property
    def remote_address(self) -> str:
        """Remote address"""
        return self._transport.remote_address

    async def receive(self) -> Msg:
        """Receive incomming message

        Raises:
            ConnectionClosedError

        """
        try:
            return await self._msg_queue.get()
        except aio.QueueClosedError:
            raise ConnectionClosedError()

    def send(self,
             msg_data: Data,
             *,
             conv: typing.Optional[Conversation] = None,
             last: bool = True,
             token: bool = True,
             timeout: typing.Optional[float] = None,
             timeout_cb: typing.Optional[typing.Callable[[Conversation],
                                                         None]] = None
             ) -> Conversation:
        """Send message

        If `conv` is ``None``, new conversation is created.

        `timeout` represents conversation timeout in seconds. If this argument
        is ``None``, conversation timeout will not be triggered. Conversation
        timeout callbacks are triggered only for opened connection. Once
        connection is closed, all active conversations are closed without
        triggering timeout callbacks.

        Raises:
            ConnectionClosedError
            Exception

        """
        mlog.debug("sending message")
        if self.is_closed:
            raise ConnectionClosedError()

        mlog.debug("setting message parameters")
        send_msg = {
            'id': self._last_id + 1,
            'first': conv.first_id if conv else self._last_id + 1,
            'owner': conv.owner if conv else True,
            'token': token,
            'last': last,
            'data': {
                'module': _value_to_sbs_maybe(msg_data.module),
                'type': msg_data.type,
                'data': self._sbs_repo.encode(msg_data.module, msg_data.type,
                                              msg_data.data)
            }
        }
        self._transport.write(send_msg)
        self._last_id += 1
        mlog.debug("message sent (id: %s)", send_msg['id'])

        if not conv:
            mlog.debug("creating new conversation")
            conv = Conversation(self, True, self._last_id)
        conv_timeout = self._conv_timeouts.pop(conv, None)
        if conv_timeout:
            mlog.debug("canceling existing conversation timeout")
            conv_timeout.cancel()
        if not last and timeout and timeout_cb:
            mlog.debug("registering conversation timeout")

            def on_conv_timeout():
                mlog.debug("conversation's timeout triggered")
                if self._conv_timeouts.pop(conv, None):
                    timeout_cb(conv)

            self._conv_timeouts[conv] = asyncio.get_event_loop().call_later(
                timeout, on_conv_timeout)

        return conv

    def _close(self):
        self._async_group.close()

    async def _read_loop(self):
        mlog.debug("connection's read loop started")

        try:
            while True:
                mlog.debug("waiting for incoming message")
                try:
                    transport_msg = await self._transport.read()
                    msg = Msg(
                        conn=self,
                        data=Data(module=transport_msg['data']['module'][1],
                                  type=transport_msg['data']['type'],
                                  data=self._sbs_repo.decode(
                                    transport_msg['data']['module'][1],
                                    transport_msg['data']['type'],
                                    transport_msg['data']['data'])),
                        conv=Conversation(conn=self,
                                          owner=not transport_msg['owner'],
                                          first_id=transport_msg['first']),
                        first=(transport_msg['owner'] and
                               transport_msg['first'] == transport_msg['id']),
                        last=transport_msg['last'],
                        token=transport_msg['token'])
                except asyncio.CancelledError:
                    raise
                except asyncio.IncompleteReadError:
                    mlog.debug("closed connection detected while reading")
                    break
                except Exception as e:
                    mlog.error("error while reading message: %s",
                               e, exc_info=e)
                    break

                conv_timeout = self._conv_timeouts.pop(msg.conv, None)
                if conv_timeout:
                    mlog.debug("canceling existing conversation timeout")
                    conv_timeout.cancel()

                if msg.data.module == 'HatPing':
                    if msg.data.type == 'MsgPing':
                        mlog.debug(
                            "received ping request - sending ping response")
                        self.send(Data('HatPing', 'MsgPong', None),
                                  conv=msg.conv)
                    elif msg.data.type == 'MsgPong':
                        mlog.debug("received ping response")
                else:
                    await self._msg_queue.put(msg)
        except asyncio.CancelledError:
            mlog.debug("read loop canceled - closing connection")
            raise
        finally:
            mlog.debug("connection's read loop stopping")
            await aio.uncancellable(self._transport.async_close(),
                                    raise_cancel=False)
            for conv_timeout in self._conv_timeouts.values():
                conv_timeout.cancel()
            self._msg_queue.close()
            self._conv_timeouts = {}
            self._close()

    async def _ping_loop(self, timeout):
        if not timeout:
            return

        def on_conv_timeout(conv):
            mlog.debug("ping response timeout - closing connection")
            self._close()

        mlog.debug("ping loop started")
        with contextlib.suppress(asyncio.CancelledError):
            while not self.is_closed:
                mlog.debug("waiting for %ss", timeout)
                await asyncio.sleep(timeout)
                mlog.debug("sending ping request")
                if self.is_closed:
                    break
                self.send(Data('HatPing', 'MsgPing', None),
                          last=False, timeout=timeout,
                          timeout_cb=on_conv_timeout)

        mlog.debug("ping loop stopping")
        self._close()


class _TcpTransport:

    def __init__(self, sbs_repo, reader, writer):
        self._sbs_repo = sbs_repo
        self._reader = reader
        self._writer = writer
        scheme = ('tcp+sbs' if writer.get_extra_info('sslcontext') is None
                  else 'ssl+sbs')
        self._local_address = _convert_sock_info_to_address(
            writer.get_extra_info('sockname'), scheme)
        self._remote_address = _convert_sock_info_to_address(
            writer.get_extra_info('peername'), scheme)

    @property
    def local_address(self):
        return self._local_address

    @property
    def remote_address(self):
        return self._remote_address

    async def read(self):
        msg_len_len = (await self._reader.readexactly(1))[0]
        msg_len_bytes = await self._reader.readexactly(msg_len_len)
        msg_len = _bebytes_to_uint(msg_len_bytes)
        msg_bytes = await self._reader.readexactly(msg_len)
        msg = self._sbs_repo.decode('Hat', 'Msg', msg_bytes)
        return msg

    def write(self, msg):
        msg_bytes = self._sbs_repo.encode('Hat', 'Msg', msg)
        msg_len = len(msg_bytes)
        msg_len_bytes = _uint_to_bebytes(msg_len)
        msg_len_len_bytes = bytes([len(msg_len_bytes)])
        self._writer.write(msg_len_len_bytes + msg_len_bytes + msg_bytes)

    async def async_close(self):
        self._writer.close()
        await self._writer.wait_closed()


def _convert_sock_info_to_address(sock_info, scheme):
    host, port = sock_info[0], sock_info[1]
    if ':' in host:
        host = '[' + host + ']'
    return '{}://{}:{}'.format(scheme, host, port)


def _create_ssl_context(pem_file):
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
    ssl_ctx.verify_mode = ssl.VerifyMode.CERT_NONE
    if pem_file:
        ssl_ctx.load_cert_chain(pem_file)
    return ssl_ctx


def _value_to_sbs_maybe(value):
    return ('Just', value) if value is not None else ('Nothing', None)


def _uint_to_bebytes(x):
    bytes_len = max(math.ceil(x.bit_length() / 8), 1)
    return x.to_bytes(bytes_len, 'big')


def _bebytes_to_uint(b):
    return int.from_bytes(b, 'big')


def _async_group_exception_cb(e):
    mlog.error('async group exception: %s', e, exc_info=e)
