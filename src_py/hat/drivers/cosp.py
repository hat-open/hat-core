"""Connection oriented session protocol

Attributes:
    mlog (logging.Logger): module logger

"""

import contextlib
import enum
import logging
import typing

from hat import util
from hat.drivers import cotp
from hat.util import aio


mlog = logging.getLogger(__name__)


Data = cotp.Data
"""Data"""


Address = cotp.Address
"""Address"""


ConnectionInfo = util.namedtuple(
    'ConnectionInfo',
    ['local_addr', "Address: local address"],
    ['local_tsel', "Optional[int]: local COTP selector"],
    ['local_ssel', "Optional[int]: local COSP selector"],
    ['remote_addr', "Address: remote address"],
    ['remote_tsel', "Optional[int]: remote COTP selector"],
    ['remote_ssel', "Optional[int]: remote COSP selector"])


ValidateResult = typing.Optional[Data]
"""Validate result"""


ValidateCb = aio.AsyncCallable[[Data], ValidateResult]
"""Validate callback"""


ConnectionCb = aio.AsyncCallable[['Connection'], None]
"""Connection callback"""


async def connect(addr, local_tsel=None, remote_tsel=None,
                  local_ssel=None, remote_ssel=None, user_data=None):
    """Connect to COSP server

    Args:
        addr (Address): remote address
        local_tsel (Optional[int]): local COTP selector
        remote_tsel (Optional[int]): remote COTP selector
        local_ssel (Optional[int]): local COSP selector
        remote_ssel (Optional[int]): remote COSP selector
        user_data (Optional[Data]): connect request user data

    Returns:
        Connection

    """
    cotp_conn = await cotp.connect(addr=addr,
                                   local_tsel=local_tsel,
                                   remote_tsel=remote_tsel)
    try:
        conn = await _create_outgoing_connection(cotp_conn, local_ssel,
                                                 remote_ssel, user_data)
        return conn
    except BaseException:
        await aio.uncancellable(_close_connection(cotp_conn, _ab_spdu))
        raise


async def listen(validate_cb, connection_cb, addr=Address('0.0.0.0', 102)):
    """Create COSP listening server

    Args:
        validate_cb (ValidateCb): callback function or coroutine called on new
            incomming connection request prior to creating new connection
        connection_cb (ConnectionCb): new connection callback
        addr (Address): local listening address

    Returns:
        Server

    """

    async def on_connection(cotp_conn):
        try:
            try:
                conn = await _create_incomming_connection(validate_cb,
                                                          cotp_conn)
            except BaseException:
                await aio.uncancellable(_close_connection(cotp_conn, _ab_spdu))
                raise
            try:
                await aio.call(connection_cb, conn)
            except BaseException:
                await aio.uncancellable(conn.async_close())
                raise
        except Exception as e:
            mlog.error("error creating new incomming connection: %s", e,
                       exc_info=e)

    async def wait_cotp_server_closed():
        try:
            await cotp_server.closed
        finally:
            group.close()

    group = aio.Group()
    cotp_server = await cotp.listen(on_connection, addr)
    group.spawn(aio.call_on_cancel, cotp_server.async_close)
    group.spawn(wait_cotp_server_closed)

    srv = Server()
    srv._group = group
    srv._cotp_server = cotp_server
    return srv


class Server:
    """COSP listening server

    For creating new server see :func:`listen`

    """

    @property
    def addresses(self):
        """List[Address]: listening addresses"""
        return self._cotp_server.addresses

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._group.closed

    async def async_close(self):
        """Close listening socket

        Calling this method doesn't close active incomming connections

        """
        await self._group.async_close()


def _create_connection(cotp_conn, cn_spdu, ac_spdu, local_ssel, remote_ssel):
    conn = Connection()
    conn._cotp_conn = cotp_conn
    conn._conn_req_user_data = cn_spdu.user_data
    conn._conn_res_user_data = ac_spdu.user_data
    conn._info = ConnectionInfo(local_ssel=local_ssel,
                                remote_ssel=remote_ssel,
                                **cotp_conn.info._asdict())
    conn._close_spdu = None
    conn._read_queue = aio.Queue()
    conn._group = aio.Group()
    conn._group.spawn(conn._read_loop)
    return conn


class Connection:
    """COSP connection

    For creating new connection see :func:`hat.drivers.cosp.connect`

    """

    @property
    def info(self):
        """ConnectionInfo: connection info"""
        return self._info

    @property
    def conn_req_user_data(self):
        """Data: connect request's user data"""
        return self._conn_req_user_data

    @property
    def conn_res_user_data(self):
        """Data: connect response's user data"""
        return self._conn_res_user_data

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._group.closed

    async def async_close(self, user_data=None):
        """Async close

        Args:
            user_data (Optional[Data]): finish message user data

        """
        self._close_spdu = _Spdu(_SpduType.FN,
                                 transport_disconnect=True,
                                 user_data=user_data)
        await self._group.async_close()

    async def read(self):
        """Read data

        Returns:
            Data

        """
        return await self._read_queue.get()

    def write(self, data):
        """Write data

        Args:
            data (Data): data

        """
        buff = bytearray(_give_tokens_spdu_data)
        buff.extend(_encode(_Spdu(type=_SpduType.DT,
                                  data=data)))
        self._cotp_conn.write(buff)

    async def _read_loop(self):
        try:
            data = bytearray()
            while True:
                spdu_data = await self._cotp_conn.read()
                spdu = _decode(memoryview(spdu_data))
                if spdu.type == _SpduType.DT:
                    data.extend(spdu.data)
                    if spdu.end is None or spdu.end:
                        await self._read_queue.put(data)
                        data = bytearray()
                elif spdu.type == _SpduType.FN:
                    self._close_spdu = _dn_spdu
                    break
                elif spdu.type == _SpduType.AB:
                    self._close_spdu = None
                    break
                else:
                    self._close_spdu = _ab_spdu
                    break
        finally:
            self._group.close()
            self._read_queue.close()
            await aio.uncancellable(
                _close_connection(self._cotp_conn, self._close_spdu))


async def _create_outgoing_connection(cotp_conn, local_ssel, remote_ssel,
                                      user_data):
    cn_spdu = _Spdu(_SpduType.CN,
                    extended_spdus=False,
                    version_number=_params_version,
                    requirements=_params_requirements,
                    calling_ssel=local_ssel,
                    called_ssel=remote_ssel,
                    user_data=user_data)
    cotp_conn.write(_encode(cn_spdu))
    ac_spdu_data = await cotp_conn.read()
    ac_spdu = _decode(memoryview(ac_spdu_data))
    _validate_connect_response(cn_spdu, ac_spdu)
    calling_ssel, called_ssel = _get_ssels(cn_spdu, ac_spdu)
    return _create_connection(cotp_conn, cn_spdu, ac_spdu,
                              calling_ssel, called_ssel)


async def _create_incomming_connection(validate_cb, cotp_conn):
    cn_spdu_data = await cotp_conn.read()
    cn_spdu = _decode(memoryview(cn_spdu_data))
    _validate_connect_request(cn_spdu)
    res_user_data = await aio.call(validate_cb, cn_spdu.user_data)
    ac_spdu = _Spdu(_SpduType.AC,
                    extended_spdus=False,
                    version_number=_params_version,
                    requirements=_params_requirements,
                    calling_ssel=cn_spdu.calling_ssel,
                    called_ssel=cn_spdu.called_ssel,
                    user_data=res_user_data)
    cotp_conn.write(_encode(ac_spdu))
    calling_ssel, called_ssel = _get_ssels(cn_spdu, ac_spdu)
    return _create_connection(cotp_conn, cn_spdu, ac_spdu,
                              called_ssel, calling_ssel)


async def _close_connection(cotp_conn, spdu):
    if spdu:
        data = _encode(spdu)
        with contextlib.suppress(Exception):
            cotp_conn.write(data)
    await cotp_conn.async_close()


def _get_ssels(cn_spdu, ac_spdu):
    calling_ssel = (cn_spdu.calling_ssel
                    if cn_spdu.calling_ssel is not None
                    else ac_spdu.calling_ssel)
    called_ssel = (cn_spdu.called_ssel
                   if cn_spdu.called_ssel is not None
                   else ac_spdu.called_ssel)
    return calling_ssel, called_ssel


def _validate_connect_request(cn_spdu):
    if cn_spdu.type != _SpduType.CN:
        raise Exception("received message is not of type CN")


def _validate_connect_response(cn_spdu, ac_spdu):
    if ac_spdu.type != _SpduType.AC:
        raise Exception("received message is not of type AC")
    if (cn_spdu.calling_ssel is not None and
            ac_spdu.calling_ssel is not None and
            cn_spdu.calling_ssel != ac_spdu.calling_ssel):
        raise Exception(f"received calling ssel  {ac_spdu.calling_ssel} "
                        f"(expecting {cn_spdu.calling_ssel})")
    if (cn_spdu.called_ssel is not None and
            ac_spdu.called_ssel is not None and
            cn_spdu.called_ssel != ac_spdu.called_ssel):
        raise Exception(f"received calling ssel {ac_spdu.called_ssel} "
                        f"(expecting {cn_spdu.called_ssel})")


class _SpduType(enum.Enum):
    CN = 13
    AC = 14
    RF = 12
    FN = 9
    DN = 10
    NF = 8
    AB = 25
    DT = 1


_Spdu = util.namedtuple(
    '_Spdu',
    ['type', "_SpduType"],
    ['extended_spdus', "Optional[bool]", None],
    ['version_number', "Optional[int]", None],
    ['transport_disconnect', "Optional[bool]", None],
    ['requirements', "Optional[Data]", None],
    ['beginning', "Optional[bool]", None],
    ['end', "Optional[bool]", None],
    ['calling_ssel', "Optional[int]", None],
    ['called_ssel', "Optional[int]", None],
    ['user_data', "Optional[Data]", None],
    ['data', "Data", b''])


def _encode(spdu):
    params = bytearray()

    conn_acc = bytearray()
    if spdu.extended_spdus is not None:
        _encode_param(conn_acc, 19, [1] if spdu.extended_spdus else [0])
    if spdu.version_number is not None:
        _encode_param(conn_acc, 22, [spdu.version_number])
    if conn_acc:
        _encode_param(params, 5, conn_acc)

    if spdu.transport_disconnect is not None:
        _encode_param(params, 17, [1 if spdu.transport_disconnect else 0])
    if spdu.requirements is not None:
        _encode_param(params, 20, spdu.requirements)
    if spdu.beginning is not None and spdu.end is not None:
        _encode_param(params, 25, [(1 if spdu.beginning else 0) |
                                   (2 if spdu.end else 0)])
    if spdu.calling_ssel is not None:
        _encode_param(params, 51, spdu.calling_ssel.to_bytes(2, 'big'))
    if spdu.called_ssel is not None:
        _encode_param(params, 52, spdu.called_ssel.to_bytes(2, 'big'))
    if spdu.user_data is not None:
        _encode_param(params, 193, spdu.user_data)

    buff = bytearray()
    buff.append(spdu.type.value)
    _encode_length(buff, params)
    buff.extend(params)
    buff.extend(spdu.data)
    return buff


def _decode(data):
    if data[:len(_give_tokens_spdu_data)] == _give_tokens_spdu_data:
        data = data[len(_give_tokens_spdu_data):]

    spdu_type, data = _SpduType(data[0]), data[1:]
    params_length, data = _decode_length(data)
    params, data = data[:params_length], data[params_length:]

    extended_spdus = None
    version_number = None
    transport_disconnect = None
    requirements = None
    beginning = None
    end = None
    calling_ssel = None
    called_ssel = None
    user_data = None
    while params:
        code, param, params = _decode_param(params)
        if code == 5:
            conn_acc = param
            while conn_acc:
                code, param, conn_acc = _decode_param(conn_acc)
                if code == 19:
                    extended_spdus = bool(param[0])
                elif code == 22:
                    version_number = param[0]
        elif code == 17:
            transport_disconnect = bool(param[0])
        elif code == 20:
            requirements = param
        elif code == 25:
            beginning = bool(param[0] & 1)
            end = bool(param[0] & 2)
        elif code == 51:
            calling_ssel = int.from_bytes(param, 'big')
        elif code == 52:
            called_ssel = int.from_bytes(param, 'big')
        elif code == 193:
            user_data = param

    return _Spdu(type=spdu_type,
                 extended_spdus=extended_spdus,
                 version_number=version_number,
                 transport_disconnect=transport_disconnect,
                 requirements=requirements,
                 beginning=beginning,
                 end=end,
                 calling_ssel=calling_ssel,
                 called_ssel=called_ssel,
                 user_data=user_data,
                 data=data)


def _encode_param(buff, code, data):
    buff.append(code)
    _encode_length(buff, data)
    buff.extend(data)


def _decode_param(data):
    code, data = data[0], data[1:]
    length, data = _decode_length(data)
    return code, data[:length], data[length:]


def _encode_length(buff, data):
    li = len(data)
    if li < 0xFF:
        buff.append(li)
    else:
        buff.extend([0xFF, li >> 8, li & 0xFF])


def _decode_length(data):
    if data[0] != 0xFF:
        return data[0], data[1:]
    return ((data[1] << 8) | data[2]), data[3:]


_give_tokens_spdu_data = b'\x01\x00'
_params_requirements = b'\x00\x02'
_params_version = 2
_ab_spdu = _Spdu(_SpduType.AB, transport_disconnect=True)
_dn_spdu = _Spdu(_SpduType.DN)
