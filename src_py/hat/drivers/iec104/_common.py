"""IEC 60870-5-104 low-level functions and data structures"""

import collections
import enum
import struct
import itertools
import contextlib
import logging
import asyncio

from hat import aio
from hat import util
from hat.drivers.iec104 import common


mlog = logging.getLogger(__name__)


class ApduFunctionType(enum.Enum):
    TESTFR_CON = 0x83
    TESTFR_ACT = 0x43
    STOPDT_CON = 0x23
    STOPDT_ACT = 0x13
    STARTDT_CON = 0x0B
    STARTDT_ACT = 0x07


class AsduType(enum.Enum):
    M_SP_NA = 1
    M_DP_NA = 3
    M_ST_NA = 5
    M_BO_NA = 7
    M_ME_NA = 9
    M_ME_NB = 11
    M_ME_NC = 13
    M_IT_NA = 15
    M_ME_ND = 21
    M_SP_TB = 30
    M_DP_TB = 31
    M_ST_TB = 32
    M_BO_TB = 33
    M_ME_TD = 34
    M_ME_TE = 35
    M_ME_TF = 36
    M_IT_TB = 37
    C_SC_NA = 45
    C_DC_NA = 46
    C_RC_NA = 47
    C_SE_NA = 48
    C_SE_NB = 49
    C_SE_NC = 50
    C_SC_TA = 58
    C_DC_TA = 59
    C_RC_TA = 60
    C_SE_TA = 61
    C_SE_TB = 62
    C_SE_TC = 63
    M_EI_NA = 70
    C_IC_NA = 100
    C_CI_NA = 101


APDUI = collections.namedtuple('APDUI', ['ssn', 'rsn', 'asdu'])

APDUS = collections.namedtuple('APDUS', ['rsn'])

APDUU = collections.namedtuple('APDUU', ['function'])

ASDU = collections.namedtuple('ASDU', [
    'type', 'cause', 'is_negative_confirm', 'is_test',
    'originator_address', 'address', 'ios'])

IO = collections.namedtuple('IO', ['address', 'elements', 'time'])


async def read_apdu(reader):
    start_byte = await reader.readexactly(1)
    if start_byte[0] != 0x68:
        raise Exception('Invalid start identifier')
    length = await reader.readexactly(1)
    if length[0] < 4:
        raise Exception("Invalid APDU length")
    control_fields = await reader.readexactly(4)
    asdu_bytes = (
        await reader.readexactly(length[0] - 4) if length[0] > 4
        else None)
    return _parse_apdu(control_fields, asdu_bytes)


def write_apdu(writer, apdu):
    apdu_bytes = bytes(_apdu_byte_iter(apdu))
    writer.write(bytes([0x68, len(apdu_bytes)]))
    writer.write(apdu_bytes)


def create_io_element(asdu_type, *vargs, **kwargs):
    return _io_element_cls[asdu_type](*vargs, **kwargs)


class Transport(aio.Resource):

    def __init__(self, reader, writer, always_enabled, response_timeout,
                 supervisory_timeout, test_timeout, send_window_size,
                 receive_window_size):
        self._reader = reader
        self._writer = writer
        self._always_enabled = always_enabled
        self._is_enabled = always_enabled
        self._response_timeout = response_timeout
        self._supervisory_timeout = supervisory_timeout
        self._test_timeout = test_timeout
        self._send_window_size = send_window_size
        self._receive_window_size = receive_window_size
        self._test_con_queue = aio.Queue()
        self._asdu_queue = aio.Queue()
        self._write_queue = aio.Queue()
        self._ssn = 0
        self._rsn = 0
        self._ack = 0
        self._w = 0
        self._write_supervisory_handle = None
        self._waiting_ack_handles = {}
        self._waiting_ack_cv = asyncio.Condition()
        self._async_group = aio.Group(
            lambda e: mlog.error('exception in transport: %s', e, exc_info=e))
        self._async_group.spawn(self._read_loop)
        self._async_group.spawn(self._write_loop)
        self._async_group.spawn(self._test_loop)
        self._async_group.spawn(aio.call_on_cancel, self._cleanup)

    @property
    def async_group(self):
        return self._async_group

    def write(self, asdu):
        self._write_queue.put_nowait(asdu)

    async def read(self):
        if self.is_closed:
            return None
        return await self._asdu_queue.get()

    async def _cleanup(self):
        for f in self._waiting_ack_handles.values():
            f.cancel()
        if self._writer.can_write_eof():
            with contextlib.suppress(Exception):
                self._writer.write_eof()
        with contextlib.suppress(Exception):
            await self._writer.drain()
        with contextlib.suppress(Exception):
            self._writer.close()
        self._asdu_queue.put_nowait(None)

    async def _test_loop(self):
        try:
            while True:
                await asyncio.sleep(self._test_timeout)
                write_apdu(self._writer, APDUU(
                    function=ApduFunctionType.TESTFR_ACT))
                while not self._test_con_queue.empty():
                    self._test_con_queue.get_nowait()
                await asyncio.wait_for(
                    self._test_con_queue.get(), self._response_timeout)
        except Exception as e:
            mlog.debug('closing transport due to exception in test loop: %s',
                       e, exc_info=e)
        finally:
            self._async_group.close()

    async def _read_loop(self):
        try:
            while True:
                apdu = await read_apdu(self._reader)
                if isinstance(apdu, APDUU):
                    if apdu.function == ApduFunctionType.STARTDT_ACT:
                        if not self._always_enabled:
                            self._is_enabled = True
                            write_apdu(self._writer, APDUU(
                                function=ApduFunctionType.STARTDT_CON))
                    elif apdu.function == ApduFunctionType.STOPDT_ACT:
                        if not self._always_enabled:
                            self._is_enabled = False
                            write_apdu(self._writer, APDUU(
                                function=ApduFunctionType.STOPDT_CON))
                    elif apdu.function == ApduFunctionType.TESTFR_ACT:
                        write_apdu(self._writer, APDUU(
                            function=ApduFunctionType.TESTFR_CON))
                    elif apdu.function == ApduFunctionType.TESTFR_CON:
                        self._test_con_queue.put_nowait(None)
                elif isinstance(apdu, APDUS):
                    await self._set_ack(apdu.rsn)
                else:
                    await self._set_ack(apdu.rsn)
                    self._set_rsn((apdu.ssn + 1) % 0x8000)
                    if apdu.asdu:
                        self._asdu_queue.put_nowait(apdu.asdu)
                    self._w += 1
                    if self._w >= self._receive_window_size:
                        write_apdu(self._writer, APDUS(rsn=self._rsn))
                        self._w = 0
                        if self._write_supervisory_handle:
                            self._write_supervisory_handle.cancel()
                            self._write_supervisory_handle = None
        except asyncio.IncompleteReadError:
            pass
        finally:
            self._async_group.close()

    async def _write_loop(self):
        try:
            while True:
                asdu = await self._write_queue.get()
                if self._ssn in self._waiting_ack_handles:
                    raise Exception("can not reuse already registered ssn")
                async with self._waiting_ack_cv:
                    while (len(self._waiting_ack_handles) >=
                            self._send_window_size):
                        await self._waiting_ack_cv.wait()
                if not self._is_enabled:
                    continue
                write_apdu(self._writer, APDUI(
                    ssn=self._ssn,
                    rsn=self._rsn,
                    asdu=asdu))
                self._w = 0
                if self._write_supervisory_handle:
                    self._write_supervisory_handle.cancel()
                    self._write_supervisory_handle = None
                self._waiting_ack_handles[self._ssn] = (
                    asyncio.get_event_loop().call_later(
                        self._response_timeout, self._on_response_timeout))
                self._ssn = (self._ssn + 1) % 0x8000
        finally:
            self._async_group.close()

    def _on_response_timeout(self):
        mlog.warn("response timeout occured - closing connection")
        self._async_group.close()

    def _on_supervisory_timeout(self):
        with contextlib.suppress(Exception):
            self._write_supervisory_handle = None
            write_apdu(self._writer, APDUS(rsn=self._rsn))
            self._w = 0

    def _set_rsn(self, rsn):
        self._rsn = rsn
        if not self._write_supervisory_handle:
            self._write_supervisory_handle = (
                asyncio.get_event_loop().call_later(
                    self._supervisory_timeout, self._on_supervisory_timeout))

    async def _set_ack(self, ack):
        for i in itertools.takewhile(
                lambda x: x != ack,
                itertools.chain(
                    range(self._ack, 0x8000),
                    range(ack),
                    [ack])):
            handle = self._waiting_ack_handles.pop(i, None)
            if not handle:
                mlog.warn("received acknowledge for unsent sequence "
                          "number - closing connection")
                self._async_group.close()
                continue
            handle.cancel()
        self._ack = ack
        async with self._waiting_ack_cv:
            self._waiting_ack_cv.notify_all()


_IOElementDef = collections.namedtuple('_IOElementDef', [
    'fields', 'size', 'has_time', 'parse_fn', 'byte_iter_fn'])


def _parse_apdu(control_fields, asdu_bytes):
    if not (control_fields[0] & 1):
        try:
            asdu = _parse_asdu(asdu_bytes)
        except Exception as e:
            asdu = None
            mlog.warn("Could not decode ASDU: %s", e, exc_info=True)
        return APDUI(
            ssn=(control_fields[1] << 7) | (control_fields[0] >> 1),
            rsn=(control_fields[3] << 7) | (control_fields[2] >> 1),
            asdu=asdu)
    if not (control_fields[0] & 2):
        return APDUS(
            rsn=(control_fields[3] << 7) | (control_fields[2] >> 1))
    return APDUU(function=ApduFunctionType(control_fields[0]))


def _apdu_byte_iter(apdu):
    if hasattr(apdu, 'ssn'):
        return itertools.chain(
            ((apdu.ssn << 1) & 0xFF,
             (apdu.ssn >> 7) & 0xFF,
             (apdu.rsn << 1) & 0xFF,
             (apdu.rsn >> 7) & 0xFF),
            _asdu_byte_iter(apdu.asdu))
    elif hasattr(apdu, 'rsn'):
        return (1, 0, (apdu.rsn << 1) & 0xFF, (apdu.rsn >> 7) & 0xFF)
    elif hasattr(apdu, 'function'):
        return (apdu.function.value, 0, 0, 0)


def _parse_asdu(asdu_bytes):
    asdu_type = AsduType(asdu_bytes[0])
    io_number = asdu_bytes[1] & 0x7F
    is_sequence = bool(asdu_bytes[1] & 0x80)
    io_count = 1 if is_sequence else io_number
    ioe_element_count = io_number if is_sequence else 1
    io_size = _io_bytes_size(asdu_type, ioe_element_count)
    ios = []
    for i in range(io_count):
        io_bytes = asdu_bytes[6 + i * io_size:
                              6 + (i + 1) * io_size]
        try:
            ios.append(_parse_io(asdu_type, io_bytes, ioe_element_count))
        except Exception as e:
            mlog.warn("Could not decode IO: %s", e, exc_info=True)
    return ASDU(
        type=asdu_type,
        cause=common.Cause(asdu_bytes[2] & 0x3F),
        is_negative_confirm=bool(asdu_bytes[2] & 0x40),
        is_test=bool(asdu_bytes[2] & 0x80),
        originator_address=asdu_bytes[3],
        address=(asdu_bytes[5] << 8) | asdu_bytes[4],
        ios=ios)


def _asdu_byte_iter(asdu):
    is_sequence = len(asdu.ios) == 1 and len(asdu.ios[0].elements) > 1
    if asdu.ios and not is_sequence and util.first(
            asdu.ios, lambda x: len(asdu.ios[0].elements) != len(x.elements)):
        raise Exception('Invalid ASDU')
    qualifier = ((0x80 if is_sequence else 0) |
                 (len(asdu.ios[0].elements) if is_sequence else len(asdu.ios)))
    cause = ((0x80 if asdu.is_test else 0) |
             (0x40 if asdu.is_negative_confirm else 0) |
             asdu.cause.value)
    originator_address = (
        asdu.originator_address if asdu.originator_address else 0)
    address = ((asdu.address >> (8 * i)) & 0xFF for i in range(2))
    ios = itertools.chain.from_iterable(
        _io_byte_iter(io, asdu.type) for io in asdu.ios)
    return itertools.chain(
        (asdu.type.value, qualifier, cause, originator_address),
        address,
        ios)


def _parse_io(asdu_type, io_bytes, elements_number):
    ioe_def = _io_element_defs[asdu_type]
    ioe_cls = _io_element_cls[asdu_type]
    address = (io_bytes[2] << 16) | (io_bytes[1] << 8) | io_bytes[0]
    elements = [ioe_cls(**ioe_def.parse_fn(ioe_bytes))
                for ioe_bytes in (
                    io_bytes[
                        3 + i * ioe_def.size:
                        3 + (i + 1) * ioe_def.size]
                    for i in range(elements_number))]
    time = (_parse_time(
                io_bytes[
                    3 + elements_number * ioe_def.size:
                    3 + elements_number * ioe_def.size + 7])
            if ioe_def.has_time else None)
    return IO(address, elements, time)


def _io_byte_iter(io, asdu_type):
    ioe_def = _io_element_defs[asdu_type]
    address = ((io.address >> (8 * i)) & 0xFF for i in range(3))
    elements = itertools.chain.from_iterable(
        ioe_def.byte_iter_fn(ioe) for ioe in io.elements)
    time = _time_byte_iter(io.time) if io.time else ()
    return itertools.chain(address, elements, time)


def _io_bytes_size(asdu_type, elements_number):
    ioe_def = _io_element_defs[asdu_type]
    ioe_size = elements_number * ioe_def.size
    time_size = 7 if ioe_def.has_time else 0
    return 3 + ioe_size + time_size


def _parse_quality(quality_byte, parse_overflow):
    return common.Quality(
        invalid=bool(quality_byte & 0x80),
        not_topical=bool(quality_byte & 0x40),
        substituted=bool(quality_byte & 0x20),
        blocked=bool(quality_byte & 0x10),
        overflow=bool(quality_byte & 0x01) if parse_overflow else False)


def _quality_byte_iter(quality):
    return (
        (0x80 if quality.invalid else 0) |
        (0x40 if quality.not_topical else 0) |
        (0x20 if quality.substituted else 0) |
        (0x10 if quality.blocked else 0) |
        (0x01 if quality.overflow else 0),)


def _parse_time(time_bytes):
    return common.Time(
        milliseconds=(time_bytes[1] << 8) | time_bytes[0],
        invalid=bool(time_bytes[2] & 0x80),
        minutes=time_bytes[2] & 0x3F,
        summer_time=bool(time_bytes[3] & 0x80),
        hours=time_bytes[3] & 0x1F,
        day_of_week=time_bytes[4] >> 5,
        day_of_month=time_bytes[4] & 0x1F,
        months=time_bytes[5] & 0x0F,
        years=time_bytes[6] & 0x7F)


def _time_byte_iter(time):
    return (
        time.milliseconds & 0xFF,
        (time.milliseconds >> 8) & 0xFF,
        (0x80 if time.invalid else 0) | (time.minutes & 0x3F),
        (0x80 if time.summer_time else 0) | (time.hours & 0x1F),
        ((time.day_of_week & 0x07) << 5) | (time.day_of_month & 0x1F),
        time.months & 0x0F,
        time.years & 0x7F)


_io_element_defs = {
    AsduType.M_SP_NA: _IOElementDef(
        fields=['value', 'quality'],
        size=1,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': ioe_bytes[0] & 1,
            'quality': _parse_quality(ioe_bytes[0], False)},
        byte_iter_fn=lambda ioe:
            ((util.first(_quality_byte_iter(ioe.quality)) & 0xFE) |
             (ioe.value & 0x01), )),
    AsduType.M_DP_NA: _IOElementDef(
        fields=['value', 'quality'],
        size=1,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': ioe_bytes[0] & 3,
            'quality': _parse_quality(ioe_bytes[0], False)},
        byte_iter_fn=lambda ioe:
            ((util.first(_quality_byte_iter(ioe.quality)) & 0xFC) |
             (ioe.value & 0x03), )),
    AsduType.M_ST_NA: _IOElementDef(
        fields=['value', 't', 'quality'],
        size=2,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('b', bytes([ioe_bytes[0] & 0x7F |
                                               (0x80 if ioe_bytes[0] & 0x40
                                                else 0)]))[0],
            't': bool(ioe_bytes[0] & 0x80),
            'quality': _parse_quality(ioe_bytes[1], True)},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                ((0x80 if ioe.t else 0) | (ioe.value & 0x7F), ),
                _quality_byte_iter(ioe.quality))),
    AsduType.M_BO_NA: _IOElementDef(
        fields=['value', 'quality'],
        size=5,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': bytes(ioe_bytes[:4]),
            'quality': _parse_quality(ioe_bytes[4], True)},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                ioe.value,
                _quality_byte_iter(ioe.quality))),
    AsduType.M_ME_NA: _IOElementDef(
        fields=['value', 'quality'],
        size=3,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<h', bytes(ioe_bytes[:2]))[0] / 0x7fff,
            'quality': _parse_quality(ioe_bytes[2], True)},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<h', round(ioe.value * 0x7fff)),
                _quality_byte_iter(ioe.quality))),
    AsduType.M_ME_NB: _IOElementDef(
        fields=['value', 'quality'],
        size=3,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<h', bytes(ioe_bytes[:2]))[0],
            'quality': _parse_quality(ioe_bytes[2], True)},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<h', ioe.value),
                _quality_byte_iter(ioe.quality))),
    AsduType.M_ME_NC: _IOElementDef(
        fields=['value', 'quality'],
        size=5,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<f', bytes(ioe_bytes[:4]))[0],
            'quality': _parse_quality(ioe_bytes[4], True)},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<f', ioe.value),
                _quality_byte_iter(ioe.quality))),
    AsduType.M_IT_NA: _IOElementDef(
        fields=['value', 'sequence', 'overflow', 'adjusted', 'invalid'],
        size=5,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<i', bytes(ioe_bytes[:4]))[0],
            'invalid': bool(ioe_bytes[4] & 0x80),
            'adjusted': bool(ioe_bytes[4] & 0x40),
            'overflow': bool(ioe_bytes[4] & 0x20),
            'sequence': ioe_bytes[4] & 0x1F},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<i', ioe.value),
                ((0x80 if ioe.invalid else 0) |
                 (0x40 if ioe.adjusted else 0) |
                 (0x20 if ioe.overflow else 0) |
                 (ioe.sequence & 0x1F), ))),
    AsduType.M_ME_ND: _IOElementDef(
        fields=['value'],
        size=2,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<h', bytes(ioe_bytes[:2]))[0] / 0x7fff},
        byte_iter_fn=lambda ioe:
            struct.pack('<h', round(ioe.value * 0x7fff))),
    AsduType.M_SP_TB: _IOElementDef(
        fields=['value', 'quality'],
        size=1,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': ioe_bytes[0] & 1,
            'quality': _parse_quality(ioe_bytes[0], False)},
        byte_iter_fn=lambda ioe:
            ((util.first(_quality_byte_iter(ioe.quality)) & 0xFE) |
             (ioe.value & 0x01), )),
    AsduType.M_DP_TB: _IOElementDef(
        fields=['value', 'quality'],
        size=1,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': ioe_bytes[0] & 3,
            'quality': _parse_quality(ioe_bytes[0], False)},
        byte_iter_fn=lambda ioe:
            ((util.first(_quality_byte_iter(ioe.quality)) & 0xFC) |
             (ioe.value & 0x03), )),
    AsduType.M_ST_TB: _IOElementDef(
        fields=['value', 't', 'quality'],
        size=2,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('b', bytes([ioe_bytes[0] & 0x7F |
                                               (0x80 if ioe_bytes[0] & 0x40
                                                else 0)]))[0],
            't': bool(ioe_bytes[0] & 0x80),
            'quality': _parse_quality(ioe_bytes[1], True)},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                ((0x80 if ioe.t else 0) | (ioe.value & 0x7F), ),
                _quality_byte_iter(ioe.quality))),
    AsduType.M_BO_TB: _IOElementDef(
        fields=['value', 'quality'],
        size=5,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': bytes(ioe_bytes[:4]),
            'quality': _parse_quality(ioe_bytes[4], True)},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                ioe.value,
                _quality_byte_iter(ioe.quality))),
    AsduType.M_ME_TD: _IOElementDef(
        fields=['value', 'quality'],
        size=3,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<h', bytes(ioe_bytes[:2]))[0] / 0x7fff,
            'quality': _parse_quality(ioe_bytes[2], True)},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<h', round(ioe.value * 0x7fff)),
                _quality_byte_iter(ioe.quality))),
    AsduType.M_ME_TE: _IOElementDef(
        fields=['value', 'quality'],
        size=3,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<h', bytes(ioe_bytes[:2]))[0],
            'quality': _parse_quality(ioe_bytes[2], True)},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<h', ioe.value),
                _quality_byte_iter(ioe.quality))),
    AsduType.M_ME_TF: _IOElementDef(
        fields=['value', 'quality'],
        size=5,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<f', bytes(ioe_bytes[:4]))[0],
            'quality': _parse_quality(ioe_bytes[4], True)},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<f', ioe.value),
                _quality_byte_iter(ioe.quality))),
    AsduType.M_IT_TB: _IOElementDef(
        fields=['value', 'sequence', 'overflow', 'adjusted', 'invalid'],
        size=5,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<i', bytes(ioe_bytes[:4]))[0],
            'invalid': bool(ioe_bytes[4] & 0x80),
            'adjusted': bool(ioe_bytes[4] & 0x40),
            'overflow': bool(ioe_bytes[4] & 0x20),
            'sequence': ioe_bytes[4] & 0x1F},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<i', ioe.value),
                ((0x80 if ioe.invalid else 0) |
                 (0x40 if ioe.adjusted else 0) |
                 (0x20 if ioe.overflow else 0) |
                 (ioe.sequence & 0x1F), ))),
    AsduType.C_SC_NA: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=1,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': ioe_bytes[0] & 0x01,
            'select': bool(ioe_bytes[0] & 0x80),
            'qualifier': (ioe_bytes[0] >> 2) & 0x1F},
        byte_iter_fn=lambda ioe:
            ((0x80 if ioe.select else 0) |
             ((ioe.qualifier & 0x1F) << 2) |
             (ioe.value & 0x01), )),
    AsduType.C_DC_NA: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=1,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': ioe_bytes[0] & 0x03,
            'select': bool(ioe_bytes[0] & 0x80),
            'qualifier': (ioe_bytes[0] >> 2) & 0x1F},
        byte_iter_fn=lambda ioe:
            ((0x80 if ioe.select else 0) |
             ((ioe.qualifier & 0x1F) << 2) |
             (ioe.value & 0x03), )),
    AsduType.C_RC_NA: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=1,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': ioe_bytes[0] & 0x03,
            'select': bool(ioe_bytes[0] & 0x80),
            'qualifier': (ioe_bytes[0] >> 2) & 0x1F},
        byte_iter_fn=lambda ioe:
            ((0x80 if ioe.select else 0) |
             ((ioe.qualifier & 0x1F) << 2) |
             (ioe.value & 0x03), )),
    AsduType.C_SE_NA: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=3,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<h', bytes(ioe_bytes[:2]))[0] / 0x7fff,
            'select': bool(ioe_bytes[2] & 0x80),
            'qualifier': ioe_bytes[2] & 0x7F},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<h', round(ioe.value * 0x7fff)),
                ((0x80 if ioe.select else 0) | (ioe.qualifier & 0x7F), ))),
    AsduType.C_SE_NB: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=3,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<h', bytes(ioe_bytes[:2]))[0],
            'select': bool(ioe_bytes[2] & 0x80),
            'qualifier': ioe_bytes[2] & 0x7F},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<h', ioe.value),
                ((0x80 if ioe.select else 0) | (ioe.qualifier & 0x7F), ))),
    AsduType.C_SE_NC: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=5,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<f', bytes(ioe_bytes[:4]))[0],
            'select': bool(ioe_bytes[4] & 0x80),
            'qualifier': ioe_bytes[4] & 0x7F},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<f', ioe.value),
                ((0x80 if ioe.select else 0) | (ioe.qualifier & 0x7F), ))),
    AsduType.C_SC_TA: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=1,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': ioe_bytes[0] & 0x01,
            'select': bool(ioe_bytes[0] & 0x80),
            'qualifier': (ioe_bytes[0] >> 2) & 0x1F},
        byte_iter_fn=lambda ioe:
            ((0x80 if ioe.select else 0) |
             ((ioe.qualifier & 0x1F) << 2) |
             (ioe.value & 0x01), )),
    AsduType.C_DC_TA: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=1,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': ioe_bytes[0] & 0x03,
            'select': bool(ioe_bytes[0] & 0x80),
            'qualifier': (ioe_bytes[0] >> 2) & 0x1F},
        byte_iter_fn=lambda ioe:
            ((0x80 if ioe.select else 0) |
             ((ioe.qualifier & 0x1F) << 2) |
             (ioe.value & 0x03), )),
    AsduType.C_RC_TA: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=1,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': ioe_bytes[0] & 0x03,
            'select': bool(ioe_bytes[0] & 0x80),
            'qualifier': (ioe_bytes[0] >> 2) & 0x1F},
        byte_iter_fn=lambda ioe:
            ((0x80 if ioe.select else 0) |
             ((ioe.qualifier & 0x1F) << 2) |
             (ioe.value & 0x03), )),
    AsduType.C_SE_TA: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=3,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<h', bytes(ioe_bytes[:2]))[0] / 0x7fff,
            'select': bool(ioe_bytes[2] & 0x80),
            'qualifier': ioe_bytes[2] & 0x7F},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<h', round(ioe.value * 0x7fff)),
                ((0x80 if ioe.select else 0) | (ioe.qualifier & 0x7F), ))),
    AsduType.C_SE_TB: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=3,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<h', bytes(ioe_bytes[:2]))[0],
            'select': bool(ioe_bytes[2] & 0x80),
            'qualifier': ioe_bytes[2] & 0x7F},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<h', ioe.value),
                ((0x80 if ioe.select else 0) | (ioe.qualifier & 0x7F), ))),
    AsduType.C_SE_TC: _IOElementDef(
        fields=['value', 'select', 'qualifier'],
        size=5,
        has_time=True,
        parse_fn=lambda ioe_bytes: {
            'value': struct.unpack('<f', bytes(ioe_bytes[:4]))[0],
            'select': bool(ioe_bytes[4] & 0x80),
            'qualifier': ioe_bytes[4] & 0x7F},
        byte_iter_fn=lambda ioe:
            itertools.chain(
                struct.pack('<f', ioe.value),
                ((0x80 if ioe.select else 0) | (ioe.qualifier & 0x7F), ))),
    AsduType.M_EI_NA: _IOElementDef(
        fields=['param_change', 'cause'],
        size=1,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'param_change': bool(ioe_bytes[0] & 0x80),
            'cause': ioe_bytes[0] & 0x7F},
        byte_iter_fn=lambda ioe:
            ((0x80 if ioe.param_change else 0) | (ioe.cause & 0x7F), )),
    AsduType.C_IC_NA: _IOElementDef(
        fields=['qualifier'],
        size=1,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'qualifier': ioe_bytes[0]},
        byte_iter_fn=lambda ioe:
            (ioe.qualifier & 0xFF, )),
    AsduType.C_CI_NA: _IOElementDef(
        fields=['request', 'freeze'],
        size=1,
        has_time=False,
        parse_fn=lambda ioe_bytes: {
            'request': ioe_bytes[0] & 0x3F,
            'freeze': ioe_bytes[0] >> 6},
        byte_iter_fn=lambda ioe:
            (((ioe.freeze & 0x03) << 6) | (ioe.request & 0x3F), ))}


_io_element_cls = {
    asdu_type: collections.namedtuple(
        asdu_type.name + '_IOElement', ioe_def.fields)
    for asdu_type, ioe_def in _io_element_defs.items()}
