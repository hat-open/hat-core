"""Chatter communication protocol

This module implements basic communication infrastructure used for Hat
communication. Hat communication is based on multiple loosely coupled services.
To implement communication with other Hat components, user should always
implement independent communication service (or use one of predefined
services).

Attributes:
    mlog (logging.Logger): module logger

"""

import asyncio
import contextlib
import logging
import math
import ssl
import urllib.parse

from hat import sbs
from hat import util
from hat.util import aio


mlog = logging.getLogger(__name__)


Msg = util.namedtuple(['Msg', "Received message"],
                      ['conn', "Connection: connection"],
                      ['data', "Data: data"],
                      ['conv', "Conversation: conversation"],
                      ['first', "bool: first flag"],
                      ['last', "bool: last flag"],
                      ['token', "bool: token flag"])


Data = util.namedtuple(['Data', "Message data"],
                       ['module', "Optional[str]: SBS module name"],
                       ['type', "str: SBS type name"],
                       ['data', "Any: data"])


Conversation = util.namedtuple(['Conversation', "Conversation"],
                               ['conn', "Connection: connection"],
                               ['owner', "bool: owner flag"],
                               ['first_id', "int: first message id"])


class ConnectionClosedError(Exception):
    """Error signaling closed connection"""


def create_sbs_repo(data_sbs_repo, schemas_sbs_path=None):
    """Create chatter SBS repository

    This function creates new SBS repository containing all chatter message
    definitions and aditional message data definitions.

    Args:
        data_sbs_repo (hat.sbs.Repository): message data SBS repository
        schemas_sbs_path (Optional[pathlib.Path]): alternative schemas_sbs path

    Returns:
        hat.sbs.Repository

    """
    schemas_sbs_path = schemas_sbs_path or sbs.default_schemas_sbs_path
    return sbs.Repository(schemas_sbs_path / 'hat.sbs',
                          schemas_sbs_path / 'hat/ping.sbs',
                          data_sbs_repo)


async def connect(sbs_repo, address, *, pem_file=None, ping_timeout=20,
                  connect_timeout=5, queue_maxsize=0):
    """Connect to remote server

    `sbs_repo` should contain all definitions required for parsing chatter
    messages and message data. See :func:`create_sbs_repo`.

    Address is string formatted as `<scheme>://<host>:<port>` where

        * `<scheme>` - one of `tcp+sbs`, `ssl+sbs`
        * `<host>` - remote host's name
        * `<port>` - remote tcp port.

    PEM file is used only for ssl connection. If PEM file is not defined,
    certificate's authenticity is not established.

    If `ping_timeout` is ``None`` or 0, ping service is not registered.

    Args:
        sbs_repo (hat.sbs.Repository): chatter SBS repository
        address (str): address
        pem_file (Optional[str]): path to pem file
        ping_timeout (float): ping timeout in seconds
        connect_timeout (float): connect timeout in seconds
        queue_maxsize (int): receive message queue maximum size (0 - unlimited)

    Returns:
        Connection: newly created connection

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


async def listen(sbs_repo, address, on_connection_cb, *, pem_file=None,
                 ping_timeout=20, queue_maxsize=0):
    """Create listening server.

    `sbs_repo` is same as for :meth:`connect`.

    Address is same as for :meth:`connect`.

    If ssl connection is used, pem_file is required.

    If `ping_timeout` is ``None`` or 0, ping service is not registered.

    Args:
        sbs_repo (hat.sbs.Repository): chatter SBS repository
        address (str): address
        on_connection_cb (Callable[[Connection], None]): on connection callback
        pem_file (Optional[str]): path to pem file
        ping_timeout (float): ping timeout in seconds
        queue_maxsize (int): receive message queue maximum size (0 - unlimited)

    Returns:
        Server

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

    def connected_cb(reader, writer):
        mlog.debug("server accepted new connection")
        transport = _TcpTransport(sbs_repo, reader, writer)
        conn = _create_connection(sbs_repo, transport, ping_timeout,
                                  queue_maxsize)
        srv._conns.add(conn)
        conn.closed.add_done_callback(lambda _: srv._conns.remove(conn))
        on_connection_cb(conn)

    srv = Server()
    srv._closed = asyncio.Future()
    srv._conns = set()
    srv._srv = await asyncio.start_server(
        connected_cb, url.hostname, url.port, ssl=ssl_ctx)
    srv._addresses = [
        _convert_sock_info_to_address(socket.getsockname(), url.scheme)
        for socket in srv._srv.sockets]
    mlog.debug("listening socket created")

    return srv


class Server:
    """Server

    For creating new server see :func:`listen`.

    """

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return asyncio.shield(self._closed)

    @property
    def addresses(self):
        """List[str]: listening addresses"""
        return self._addresses

    async def async_close(self):
        """Close server and all associated connections"""
        if self._srv:
            self._srv.close()
            await self._srv.wait_closed()
            self._srv = None
        if self._conns:
            await asyncio.wait([conn.async_close() for conn in self._conns])
        if not self._closed.done():
            self._closed.set_result(True)


def _create_connection(sbs_repo, transport, ping_timeout, queue_maxsize):
    conn = Connection()
    conn._sbs_repo = sbs_repo
    conn._transport = transport
    conn._last_id = 0
    conn._conv_timeouts = {}
    conn._msg_queue = aio.Queue(maxsize=queue_maxsize)
    conn._async_group = aio.Group(
        lambda e: mlog.error('connection async group exception: %s', e,
                             exc_info=e))
    conn._async_group.spawn(conn._read_loop)
    conn._async_group.spawn(conn._ping_loop, ping_timeout)
    return conn


class Connection:
    """Single connection

    For creating new connection see :func:`connect`.

    """

    @property
    def local_address(self):
        """str: Local address"""
        return self._transport.local_address

    @property
    def remote_address(self):
        """str: Remote address"""
        return self._transport.remote_address

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    async def receive(self):
        """Receive incomming message

        Returns:
            Msg

        Raises:
            ConnectionClosedError

        """
        try:
            return await self._msg_queue.get()
        except aio.QueueClosedError:
            raise ConnectionClosedError()

    def send(self, msg_data, *, conv=None, last=True, token=True,
             timeout=None, timeout_cb=None):
        """Send message

        Conversation timeout callbacks are triggered only for opened
        connection. Once connection is closed, all active conversations are
        closed without triggering timeout callbacks.

        Sending message on closed connection will silently discard message.

        Args:
            msg_data (Data): message data
            conv (Optional[Conversation]): existing conversation
                or None for new conversation
            last (bool): conversation's last flag
            token (bool): conversation's token flag
            timeout (Optional[float]): conversation timeout in seconds or None
                for unlimited timeout
            conv_timeout_cb (Optional[Callable[[Conversation],None]]):
                conversation timeout callback

        Returns:
            Conversation

        Raises:
            ConnectionClosedError
            Exception

        """
        mlog.debug("sending message")
        if self.closed.done():
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
                        first=transport_msg['first'],
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
            while not self.closed.done():
                mlog.debug("waiting for %ss", timeout)
                await asyncio.sleep(timeout)
                mlog.debug("sending ping request")
                if self.closed.done():
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
