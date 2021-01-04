"""Connection oriented transport protocol

Attributes:
    mlog (logging.Logger): module logger

"""

import enum
import logging
import math
import typing

from hat import aio
from hat.drivers import tpkt


mlog = logging.getLogger(__name__)


Data = tpkt.Data
"""Data"""


Address = tpkt.Address
"""Address"""


class ConnectionInfo(typing.NamedTuple):
    local_addr: Address
    local_tsel: typing.Optional[int]
    remote_addr: Address
    remote_tsel: typing.Optional[int]


ConnectionCb = aio.AsyncCallable[['Connection'], None]
"""Connection callback"""


async def connect(addr: Address,
                  local_tsel: typing.Optional[int] = None,
                  remote_tsel: typing.Optional[int] = None
                  ) -> 'Connection':
    """Create new COTP connection"""
    tpkt_conn = await tpkt.connect(addr)
    try:
        conn = await _create_outgoing_connection(tpkt_conn, local_tsel,
                                                 remote_tsel)
        return conn
    except BaseException:
        await aio.uncancellable(tpkt_conn.async_close())
        raise


async def listen(connection_cb: ConnectionCb,
                 addr: Address = Address('0.0.0.0', 102)
                 ) -> 'Server':
    """Create new COTP listening server

    Args:
        connection_cb: new connection callback
        addr: local listening address

    """

    async def on_connection(tpkt_conn):
        try:
            try:
                conn = await _create_incomming_connection(tpkt_conn)
            except BaseException:
                await aio.uncancellable(tpkt_conn.async_close())
                raise
            try:
                await aio.call(connection_cb, conn)
            except BaseException:
                await aio.uncancellable(conn.async_close())
                raise
        except Exception as e:
            mlog.error("error creating new incomming connection: %s", e,
                       exc_info=e)

    async def wait_tpkt_server_closed():
        try:
            await tpkt_server.wait_closed()
        finally:
            async_group.close()

    async_group = aio.Group()
    tpkt_server = await tpkt.listen(on_connection, addr)
    async_group.spawn(aio.call_on_cancel, tpkt_server.async_close)
    async_group.spawn(wait_tpkt_server_closed)

    srv = Server()
    srv._async_group = async_group
    srv._tpkt_server = tpkt_server
    return srv


class Server(aio.Resource):
    """COTP listening server

    For creation of new instance see :func:`listen`

    Closing server doesn't close active incomming connections

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def addresses(self) -> typing.List[Address]:
        """Listening addresses"""
        return self._tpkt_server.addresses


def _create_connection(tpkt_conn, max_tpdu, local_tsel, remote_tsel):
    conn = Connection()
    conn._tpkt_conn = tpkt_conn
    conn._max_tpdu = max_tpdu
    conn._info = ConnectionInfo(local_tsel=local_tsel,
                                remote_tsel=remote_tsel,
                                **tpkt_conn.info._asdict())
    conn._read_queue = aio.Queue()
    conn._async_group = aio.Group()
    conn._async_group.spawn(conn._read_loop)
    return conn


class Connection(aio.Resource):
    """COTP connection

    For creation of new instance see :func:`connect`

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def info(self) -> ConnectionInfo:
        """Connection info"""
        return self._info

    async def read(self) -> Data:
        """Read data"""
        return await self._read_queue.get()

    def write(self, data: bytes):
        """Write data"""
        max_size = self._max_tpdu - 3
        while len(data) > 0:
            single_data, data = data[:max_size], data[max_size:]
            tpdu = _DT(eot=not data, data=single_data)
            tpdu_data = _encode(tpdu)
            self._tpkt_conn.write(tpdu_data)

    async def _read_loop(self):
        try:
            data = []
            while True:
                tpdu_data = await self._tpkt_conn.read()
                tpdu = _decode(memoryview(tpdu_data))
                if isinstance(tpdu, _DT):
                    data += tpdu.data
                    if tpdu.eot:
                        await self._read_queue.put(bytes(data))
                        data = []
                elif isinstance(tpdu, _DR) or isinstance(tpdu, _ER):
                    self._async_group.close()
                    mlog.info("received disconnect request / error")
                    break
        except Exception as e:
            mlog.error("error while reading: %s", e, exc_info=e)
        finally:
            self._async_group.close()
            self._read_queue.close()
            await aio.uncancellable(self._tpkt_conn.async_close())


_last_src = 0


async def _create_outgoing_connection(tpkt_conn, local_tsel, remote_tsel):
    global _last_src

    _last_src = _last_src + 1 if _last_src < 0xFFFF else 1
    cr_tpdu = _CR(src=_last_src,
                  cls=0,
                  calling_tsel=local_tsel,
                  called_tsel=remote_tsel,
                  max_tpdu=2048,
                  pref_max_tpdu=None)
    tpkt_conn.write(_encode(cr_tpdu))

    cc_tpdu_data = await tpkt_conn.read()
    cc_tpdu = _decode(memoryview(cc_tpdu_data))
    _validate_connect_response(cr_tpdu, cc_tpdu)

    max_tpdu = _calculate_max_tpdu(cr_tpdu, cc_tpdu)
    calling_tsel, called_tsel = _get_tsels(cr_tpdu, cc_tpdu)
    return _create_connection(tpkt_conn, max_tpdu, calling_tsel, called_tsel)


async def _create_incomming_connection(tpkt_conn):
    global _last_src

    cr_tpdu_data = await tpkt_conn.read()
    cr_tpdu = _decode(memoryview(cr_tpdu_data))
    _validate_connect_request(cr_tpdu)

    _last_src = _last_src + 1 if _last_src < 0xFFFF else 1
    cc_tpdu = _CC(dst=cr_tpdu.src,
                  src=_last_src,
                  cls=0,
                  calling_tsel=cr_tpdu.calling_tsel,
                  called_tsel=cr_tpdu.called_tsel,
                  max_tpdu=_calculate_cc_max_tpdu(cr_tpdu),
                  pref_max_tpdu=None)
    tpkt_conn.write(_encode(cc_tpdu))

    max_tpdu = _calculate_max_tpdu(cr_tpdu, cc_tpdu)
    calling_tsel, called_tsel = _get_tsels(cr_tpdu, cc_tpdu)
    return _create_connection(tpkt_conn, max_tpdu, called_tsel, calling_tsel)


class _TpduType(enum.Enum):
    DT = 0xF0
    CR = 0xE0
    CC = 0xD0
    DR = 0x80
    ER = 0x70


class _DT(typing.NamedTuple):
    """Data TPDU"""
    eot: bool
    """end of transmition flag"""
    data: Data


class _CR(typing.NamedTuple):
    """Connection request TPDU"""
    src: int
    """connection reference selectet by initiator of connection request"""
    cls: int
    """transport protocol class"""
    calling_tsel: typing.Optional[int]
    """calling transport selector"""
    called_tsel: typing.Optional[int]
    """responding transport selector"""
    max_tpdu: int
    """max tpdu size in octets"""
    pref_max_tpdu: int
    """preferred max tpdu size in octets"""


class _CC(typing.NamedTuple):
    """Connection confirm TPDU"""
    dst: int
    """connection reference selected by initiator of connection request"""
    src: int
    """connection reference selected by initiator of connection confirm"""
    cls: int
    """transport protocol class"""
    calling_tsel: typing.Optional[int]
    """calling transport selector"""
    called_tsel: typing.Optional[int]
    """responding transport selector"""
    max_tpdu: int
    """max tpdu size in octets"""
    pref_max_tpdu: int
    """preferred max tpdu size in octets"""


class _DR(typing.NamedTuple):
    """Disconnect request TPDU"""
    dst: int
    """connection reference selected by remote entity"""
    src: int
    """connection reference selected by initiator of disconnect request"""
    reason: int
    """reason for disconnection"""


class _ER(typing.NamedTuple):
    """Error TPDU"""
    dst: int
    """connection reference selected by remote entity"""
    cause: int
    """reject cause"""


def _validate_connect_request(cr_tpdu):
    if not isinstance(cr_tpdu, _CR):
        raise Exception("received message is not of type CR")
    if cr_tpdu.cls != 0:
        raise Exception(f"received class {cr_tpdu.cls} "
                        "(only class 0 is supported)")


def _validate_connect_response(cr_tpdu, cc_tpdu):
    if not isinstance(cc_tpdu, _CC):
        raise Exception("received message is not of type CC")
    if (cr_tpdu.calling_tsel is not None and
            cc_tpdu.calling_tsel is not None and
            cr_tpdu.calling_tsel != cc_tpdu.calling_tsel):
        raise Exception(f"received calling tsel {cc_tpdu.calling_tsel} "
                        f"instead of {cr_tpdu.calling_tsel}")
    if (cr_tpdu.called_tsel is not None and
            cc_tpdu.called_tsel is not None and
            cr_tpdu.called_tsel != cc_tpdu.called_tsel):
        raise Exception(f"received calling tsel {cc_tpdu.called_tsel} "
                        f"instead of {cr_tpdu.called_tsel}")
    if cc_tpdu.dst != cr_tpdu.src:
        raise Exception("received message with invalid sequence number")
    if cc_tpdu.cls != 0:
        raise Exception(f"received class {cc_tpdu.cls} "
                        f"(only class 0 is supported)")


def _calculate_max_tpdu(cr_tpdu, cc_tpdu):

    # TODO not sure about standard's definition of this calculation

    if not cr_tpdu.max_tpdu and not cc_tpdu.max_tpdu:
        return 128
    elif cr_tpdu.max_tpdu and not cc_tpdu.max_tpdu:
        return cr_tpdu.max_tpdu
    return cc_tpdu.max_tpdu


def _calculate_cc_max_tpdu(cr_tpdu):

    # TODO not sure about standard's definition of this calculation

    if cr_tpdu.max_tpdu:
        return cr_tpdu.max_tpdu
    elif cr_tpdu.pref_max_tpdu:
        return cr_tpdu.pref_max_tpdu
    return 128


def _get_tsels(cr_tpdu, cc_tpdu):
    calling_tsel = (cr_tpdu.calling_tsel
                    if cr_tpdu.calling_tsel is not None
                    else cc_tpdu.calling_tsel)
    called_tsel = (cr_tpdu.called_tsel
                   if cr_tpdu.called_tsel is not None
                   else cc_tpdu.called_tsel)
    return calling_tsel, called_tsel


def _encode(tpdu):
    if isinstance(tpdu, _DT):
        tpdu_type = _TpduType.DT
    elif isinstance(tpdu, _CR):
        tpdu_type = _TpduType.CR
    elif isinstance(tpdu, _CC):
        tpdu_type = _TpduType.CC
    elif isinstance(tpdu, _DR):
        tpdu_type = _TpduType.DR
    elif isinstance(tpdu, _ER):
        tpdu_type = _TpduType.ER
    else:
        raise ValueError('invalid tpdu')

    header = [tpdu_type.value]

    if tpdu_type == _TpduType.DT:
        header += [0x80 if tpdu.eot else 0]
        return bytes([len(header), *header, *tpdu.data])

    if tpdu_type == _TpduType.CR:
        header += [0, 0]
    else:
        header += tpdu.dst.to_bytes(2, 'big')

    if tpdu_type == _TpduType.ER:
        header += [tpdu.cause]
    else:
        header += tpdu.src.to_bytes(2, 'big')

    if tpdu_type == _TpduType.DR:
        header += [tpdu.reason]
    elif tpdu_type == _TpduType.CR or tpdu_type == _TpduType.CC:
        header += [tpdu.cls << 4]
        if tpdu.calling_tsel is not None:
            header += [0xC1, 2, *tpdu.calling_tsel.to_bytes(2, 'big')]
        if tpdu.called_tsel is not None:
            header += [0xC2, 2, *tpdu.called_tsel.to_bytes(2, 'big')]
        if tpdu.max_tpdu is not None:
            header += [0xC0, 1, tpdu.max_tpdu.bit_length() - 1]
        if tpdu.pref_max_tpdu is not None:
            pref_max_tpdu_data = _uint_to_bebytes(tpdu.pref_max_tpdu // 128)
            header += [0xC0, len(pref_max_tpdu_data), *pref_max_tpdu_data]

    return bytes([len(header), *header])


def _decode(data):
    length_indicator = data[0]
    if length_indicator >= len(data) or length_indicator > 254:
        raise ValueError("invalid length indicator")

    header = data[:length_indicator + 1]
    tpdu_data = data[length_indicator + 1:]
    tpdu_type = _TpduType(header[1] & 0xF0)

    if tpdu_type == _TpduType.DT:
        eot = bool(header[2] & 0x80)
        return _DT(eot=eot,
                   data=tpdu_data)

    if tpdu_type in (_TpduType.CR, _TpduType.CC, _TpduType.DR):
        src = (header[4] << 8) | header[5]

    if tpdu_type in (_TpduType.CC, _TpduType.DR, _TpduType.ER):
        dst = (header[2] << 8) | header[3]

    if tpdu_type in (_TpduType.CR, _TpduType.CC):
        cls = header[6] >> 4
        calling_tsel = None
        called_tsel = None
        max_tpdu = None
        pref_max_tpdu = None
        vp_data = header[7:]
        while vp_data:
            k, v, vp_data = (vp_data[0],
                             vp_data[2:2 + vp_data[1]],
                             vp_data[2 + vp_data[1]:])
            if k == 0xC1:
                calling_tsel = _bebytes_to_uint(v)
            elif k == 0xC2:
                called_tsel = _bebytes_to_uint(v)
            elif k == 0xC0:
                max_tpdu = 1 << v[0]
            elif k == 0xF0:
                pref_max_tpdu = 128 * _bebytes_to_uint(v)

    if tpdu_type == _TpduType.CR:
        return _CR(src=src,
                   cls=cls,
                   calling_tsel=calling_tsel,
                   called_tsel=called_tsel,
                   max_tpdu=max_tpdu,
                   pref_max_tpdu=pref_max_tpdu)

    if tpdu_type == _TpduType.CC:
        return _CC(dst=dst,
                   src=src,
                   cls=cls,
                   calling_tsel=calling_tsel,
                   called_tsel=called_tsel,
                   max_tpdu=max_tpdu,
                   pref_max_tpdu=pref_max_tpdu)

    if tpdu_type == _TpduType.DR:
        reason = header[6]
        return _DR(dst=dst,
                   src=src,
                   reason=reason)

    if tpdu_type == _TpduType.ER:
        cause = header[4]
        return _ER(dst=dst,
                   cause=cause)

    raise ValueError("invalid tpdu code")


def _bebytes_to_uint(b):
    return int.from_bytes(b, 'big')


def _uint_to_bebytes(x):
    bytes_len = max(math.ceil(x.bit_length() / 8), 1)
    return x.to_bytes(bytes_len, 'big')
