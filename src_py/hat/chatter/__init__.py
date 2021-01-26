"""Chatter communication protocol

This module implements basic communication infrastructure used for Hat
communication. Hat communication is based on multiple loosely coupled services.
To implement communication with other Hat components, user should always
implement independent communication service (or use one of predefined
services).

"""

from pathlib import Path
import asyncio
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
    data: Data
    conv: Conversation
    first: bool
    last: bool
    token: bool


async def connect(sbs_repo: sbs.Repository,
                  address: str,
                  *,
                  pem_file: typing.Optional[str] = None,
                  ping_timeout: float = 20,
                  queue_maxsize: int = 0
                  ) -> 'Connection':
    """Connect to remote server

    `sbs_repo` should include `hat.chatter.sbs_repo` and additional message
    data definitions.

    Address is string formatted as `<scheme>://<host>:<port>` where

        * `<scheme>` - one of `tcp+sbs`, `ssl+sbs`
        * `<host>` - remote host's name
        * `<port>` - remote tcp port.

    PEM file is used only for ssl connection. If PEM file is not defined,
    certificate's authenticity is not established.

    If `ping_timeout` is ``None`` or 0, ping service is not registered,
    otherwise it represents ping timeout in seconds.

    `queue_maxsize` represents receive message queue maximum size. If set to
    ``0``, queue size is unlimited.

    Raises:
        OSError: could not connect to specified address
        ValueError: wrong address format

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

    reader, writer = await asyncio.open_connection(url.hostname, url.port,
                                                   ssl=ssl_ctx)
    transport = _TcpTransport(sbs_repo, reader, writer)

    mlog.debug('client connection established')
    conn = _create_connection(sbs_repo, transport, ping_timeout, queue_maxsize)
    return conn


async def listen(sbs_repo: sbs.Repository,
                 address: str,
                 connection_cb: typing.Callable[['Connection'], None],
                 *,
                 pem_file: typing.Optional[str] = None,
                 ping_timeout: float = 20,
                 queue_maxsize: int = 0
                 ) -> 'Server':
    """Create listening server.

    Arguments are the same as for `connect` function with addition of
    `connection_cb` which is called once for each newly established connection.

    If SSL connection is used, `pem_file` is required.

    Raises:
        OSError: could not listen on specified address
        ValueError: wrong address format

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

    server = Server()
    server._sbs_repo = sbs_repo
    server._connection_cb = connection_cb
    server._ping_timeout = ping_timeout
    server._queue_maxsize = queue_maxsize

    server._srv = await asyncio.start_server(server._on_connected,
                                             url.hostname, url.port,
                                             ssl=ssl_ctx)

    mlog.debug("listening socket created")
    server._async_group = aio.Group()
    server._async_group.spawn(aio.call_on_cancel, server._on_close)
    server._addresses = [_sock_info_to_address(socket.getsockname(),
                                               url.scheme)
                         for socket in server._srv.sockets]

    return server


class Server(aio.Resource):
    """Server

    For creating new server see `listen` function.

    When server is closed, all incomming connections are also closed.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def addresses(self) -> typing.List[str]:
        """Listening addresses"""
        return self._addresses

    async def _on_close(self):
        self._srv.close()
        await self._srv.wait_closed()

    def _on_connected(self, reader, writer):
        mlog.debug("server accepted new connection")
        transport = _TcpTransport(self._sbs_repo, reader, writer)
        conn = _create_connection(self._sbs_repo, transport,
                                  self._ping_timeout, self._queue_maxsize,
                                  self._async_group)
        self._connection_cb(conn)


def _create_connection(sbs_repo, transport, ping_timeout, queue_maxsize,
                       parent_async_group=None):
    conn = Connection()
    conn._sbs_repo = sbs_repo
    conn._transport = transport
    conn._ping_timeout = ping_timeout
    conn._last_id = 0
    conn._conv_timeouts = {}
    conn._msg_queue = aio.Queue(maxsize=queue_maxsize)

    conn._async_group = (parent_async_group.create_subgroup()
                         if parent_async_group is not None
                         else aio.Group())
    conn._async_group.spawn(aio.call_on_cancel, transport.async_close)
    conn._async_group.spawn(conn._read_loop)
    if ping_timeout:
        conn._async_group.spawn(conn._ping_loop)

    return conn


class Connection(aio.Resource):
    """Single connection

    For creating new connection see `connect` function.

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
        """Receive incoming message

        Raises:
            ConnectionError

        """
        try:
            return await self._msg_queue.get()

        except aio.QueueClosedError:
            raise ConnectionError()

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
            ConnectionError

        """
        mlog.debug("sending message")
        if self.is_closing:
            raise ConnectionError()

        msg_id = self._last_id + 1
        msg = {'id': msg_id,
               'first': conv.first_id if conv else self._last_id + 1,
               'owner': conv.owner if conv else True,
               'token': token,
               'last': last,
               'data': {'module': _value_to_sbs_maybe(msg_data.module),
                        'type': msg_data.type,
                        'data': self._sbs_repo.encode(msg_data.module,
                                                      msg_data.type,
                                                      msg_data.data)}}

        self._transport.write(msg)
        self._last_id = msg_id
        mlog.debug("message sent (id: %s)", msg_id)

        if not conv:
            mlog.debug("creating new conversation")
            conv = Conversation(self, True, msg_id)

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

    async def _read_loop(self):
        mlog.debug("connection's read loop started")
        try:
            while True:
                mlog.debug("waiting for incoming message")
                data = await self._transport.read()
                msg = _msg_from_sbs(self._sbs_repo, self, data)

                conv_timeout = self._conv_timeouts.pop(msg.conv, None)
                if conv_timeout:
                    mlog.debug("canceling existing conversation timeout")
                    conv_timeout.cancel()

                msg_type = msg.data.module, msg.data.type

                if msg_type == ('HatPing', 'MsgPing'):
                    mlog.debug("received ping request - sending ping response")
                    self.send(Data('HatPing', 'MsgPong', None), conv=msg.conv)

                elif msg_type == ('HatPing', 'MsgPong'):
                    mlog.debug("received ping response")

                else:
                    mlog.debug("received message %s", msg_type)
                    await self._msg_queue.put(msg)

        except asyncio.IncompleteReadError:
            mlog.debug("closed connection detected while reading")

        except Exception as e:
            mlog.error("read loop error: %s", e, exc_info=e)

        finally:
            mlog.debug("connection's read loop stopping")
            self._async_group.close()
            self._msg_queue.close()
            for conv_timeout in self._conv_timeouts.values():
                conv_timeout.cancel()
            self._conv_timeouts = {}

    async def _ping_loop(self):
        mlog.debug("ping loop started")
        try:
            while True:
                mlog.debug("ping loop - waiting for %ss", self._ping_timeout)
                await asyncio.sleep(self._ping_timeout)

                mlog.debug("sending ping request")
                self.send(Data('HatPing', 'MsgPing', None),
                          last=False,
                          timeout=self._ping_timeout,
                          timeout_cb=self._on_ping_timeout)

        except ConnectionError:
            pass

        finally:
            mlog.debug("ping loop stopped")
            self._async_group.close()

    def _on_ping_timeout(self, conv):
        mlog.debug("ping response timeout - closing connection")
        self._async_group.close()


class _TcpTransport:

    def __init__(self, sbs_repo, reader, writer):
        self._sbs_repo = sbs_repo
        self._reader = reader
        self._writer = writer

        sslcontext = writer.get_extra_info('sslcontext')
        sockname = writer.get_extra_info('sockname')
        peername = writer.get_extra_info('peername')
        scheme = 'tcp+sbs' if sslcontext is None else 'ssl+sbs'

        self._local_address = _sock_info_to_address(sockname, scheme)
        self._remote_address = _sock_info_to_address(peername, scheme)

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


def _sock_info_to_address(sock_info, scheme):
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


def _msg_from_sbs(sbs_repo, conn, data):
    return Msg(data=Data(module=data['data']['module'][1],
                         type=data['data']['type'],
                         data=sbs_repo.decode(data['data']['module'][1],
                                              data['data']['type'],
                                              data['data']['data'])),
               conv=Conversation(conn=conn,
                                 owner=not data['owner'],
                                 first_id=data['first']),
               first=data['owner'] and data['first'] == data['id'],
               last=data['last'],
               token=data['token'])
