import collections
import logging
import struct

from hat import util
from hat.drivers import tcp
from hat.drivers.iec104._iec104 import common


mlog = logging.getLogger(__name__)


async def read_apdu(conn: tcp.Connection
                    ) -> common.APDU:
    start_byte = await conn.readexactly(1)
    if start_byte[0] != 0x68:
        raise Exception('invalid start identifier')

    length = await conn.readexactly(1)
    apdu_length = length[0]
    if apdu_length < 4:
        raise Exception("invalid APDU length")

    control_fields = await conn.readexactly(4)

    asdu_length = apdu_length - 4
    if asdu_length:
        asdu_bytes = await conn.readexactly(asdu_length)
    else:
        asdu_bytes = b''

    asdu_bytes = memoryview(asdu_bytes)
    return _decode_apdu(control_fields, asdu_bytes)


def write_apdu(conn: tcp.Connection,
               apdu: common.APDU):
    apdu_bytes = bytes(_encode_apdu(apdu))
    header = bytes([0x68, len(apdu_bytes)])
    conn.write(header)
    conn.write(apdu_bytes)


def _decode_apdu(control_fields, asdu_bytes):
    if control_fields[0] & 1 and control_fields[0] & 2:
        function = common.ApduFunction(control_fields[0])
        return common.APDUU(function)

    if control_fields[0] & 1:
        rsn = (control_fields[3] << 7) | (control_fields[2] >> 1)
        return common.APDUS(rsn=rsn)

    try:
        asdu = _decode_asdu(asdu_bytes)
    except Exception as e:
        mlog.warn("error decoding ASDU: %s", e, exc_info=e)
        asdu = None

    ssn = (control_fields[1] << 7) | (control_fields[0] >> 1)
    rsn = (control_fields[3] << 7) | (control_fields[2] >> 1)
    return common.APDUI(ssn=ssn,
                        rsn=rsn,
                        asdu=asdu)


def _encode_apdu(apdu):
    if isinstance(apdu, common.APDUI):
        yield (apdu.ssn << 1) & 0xFF
        yield (apdu.ssn >> 7) & 0xFF
        yield (apdu.rsn << 1) & 0xFF
        yield (apdu.rsn >> 7) & 0xFF
        yield from _encode_asdu(apdu.asdu)

    elif isinstance(apdu, common.APDUS):
        yield 1
        yield 0
        yield (apdu.rsn << 1) & 0xFF
        yield (apdu.rsn >> 7) & 0xFF

    elif isinstance(apdu, common.APDUU):
        yield apdu.function.value
        yield 0
        yield 0
        yield 0

    else:
        raise ValueError('unsupported apdu')


def _decode_asdu(asdu_bytes):
    asdu_type = common.AsduType(asdu_bytes[0])
    io_number = asdu_bytes[1] & 0x7F
    is_sequence = bool(asdu_bytes[1] & 0x80)
    io_count = 1 if is_sequence else io_number
    ioe_element_count = io_number if is_sequence else 1
    cause = common.Cause(asdu_bytes[2] & 0x3F)
    is_negative_confirm = bool(asdu_bytes[2] & 0x40)
    is_test = bool(asdu_bytes[2] & 0x80)
    originator_address = asdu_bytes[3]
    address = (asdu_bytes[5] << 8) | asdu_bytes[4]

    ios = collections.deque()
    io_bytes = asdu_bytes[6:]
    for _ in range(io_count):
        io, io_bytes = _decode_io(asdu_type, ioe_element_count, io_bytes)
        ios.append(io)

    return common.ASDU(type=asdu_type,
                       cause=cause,
                       is_negative_confirm=is_negative_confirm,
                       is_test=is_test,
                       originator_address=originator_address,
                       address=address,
                       ios=list(ios))


def _encode_asdu(asdu):
    yield asdu.type.value

    is_sequence = len(asdu.ios) == 1 and len(asdu.ios[0].elements) > 1
    if is_sequence:
        yield 0x80 | len(asdu.ios[0].elements)
    else:
        yield len(asdu.ios)

    yield ((0x80 if asdu.is_test else 0) |
           (0x40 if asdu.is_negative_confirm else 0) |
           asdu.cause.value)

    yield asdu.originator_address if asdu.originator_address else 0

    yield asdu.address & 0xFF
    yield (asdu.address >> 8) & 0xFF

    for io in asdu.ios:
        if not is_sequence and len(io.elements) != 1:
            raise Exception('invalid ASDU')
        yield from _encode_io(io)


def _decode_io(asdu_type, elements_number, io_bytes):
    address = (io_bytes[2] << 16) | (io_bytes[1] << 8) | io_bytes[0]

    elements = collections.deque()
    io_bytes = io_bytes[3:]
    for _ in range(elements_number):
        element, io_bytes = _decode_io_element(asdu_type, io_bytes)
        elements.append(element)

    if asdu_type in _asdu_types_with_time:
        time, io_bytes = _decode_time(io_bytes)
    else:
        time = None

    io = common.IO(address=address,
                   elements=list(elements),
                   time=time)
    return io, io_bytes


def _encode_io(io):
    yield io.address & 0xFF
    yield (io.address >> 8) & 0xFF
    yield (io.address >> 16) & 0xFF

    for element in io.elements:
        yield from _encode_io_element(element)

    if io.time:
        yield from _encode_time(io.time)


def _decode_io_element(asdu_type, io_bytes):
    if asdu_type == common.AsduType.M_SP_NA:
        value = common.SingleValue(io_bytes[0] & 1)
        quality, io_bytes = _decode_quality(False, io_bytes)

        element = common.IOElement_M_SP_NA(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_DP_NA:
        value = common.DoubleValue(io_bytes[0] & 3)
        quality, io_bytes = _decode_quality(False, io_bytes)

        element = common.IOElement_M_DP_NA(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_ST_NA:
        value, io_bytes = _decode_step_position_value(io_bytes)
        quality, io_bytes = _decode_quality(True, io_bytes)

        element = common.IOElement_M_ST_NA(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_BO_NA:
        value, io_bytes = _decode_bitstring_value(io_bytes)
        quality, io_bytes = _decode_quality(True, io_bytes)

        element = common.IOElement_M_BO_NA(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_ME_NA:
        value, io_bytes = _decode_normalized_value(io_bytes)
        quality, io_bytes = _decode_quality(True, io_bytes)

        element = common.IOElement_M_ME_NA(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_ME_NB:
        value, io_bytes = _decode_scaled_value(io_bytes)
        quality, io_bytes = _decode_quality(True, io_bytes)

        element = common.IOElement_M_ME_NB(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_ME_NC:
        value, io_bytes = _decode_floating_value(io_bytes)
        quality, io_bytes = _decode_quality(True, io_bytes)

        element = common.IOElement_M_ME_NC(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_IT_NA:
        value, io_bytes = _decode_binary_counter_value(io_bytes)

        element = common.IOElement_M_IT_NA(value=value)
        return element, io_bytes

    if asdu_type == common.AsduType.M_ME_ND:
        value, io_bytes = _decode_normalized_value(io_bytes)

        element = common.IOElement_M_ME_ND(value=value)
        return element, io_bytes

    if asdu_type == common.AsduType.M_SP_TB:
        value = common.SingleValue(io_bytes[0] & 1)
        quality, io_bytes = _decode_quality(False, io_bytes)

        element = common.IOElement_M_SP_TB(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_DP_TB:
        value = common.DoubleValue(io_bytes[0] & 3)
        quality, io_bytes = _decode_quality(False, io_bytes)

        element = common.IOElement_M_DP_TB(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_ST_TB:
        value, io_bytes = _decode_step_position_value(io_bytes)
        quality, io_bytes = _decode_quality(True, io_bytes)

        element = common.IOElement_M_ST_TB(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_BO_TB:
        value, io_bytes = _decode_bitstring_value(io_bytes)
        quality, io_bytes = _decode_quality(True, io_bytes)

        element = common.IOElement_M_BO_TB(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_ME_TD:
        value, io_bytes = _decode_normalized_value(io_bytes)
        quality, io_bytes = _decode_quality(True, io_bytes)

        element = common.IOElement_M_ME_TD(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_ME_TE:
        value, io_bytes = _decode_scaled_value(io_bytes)
        quality, io_bytes = _decode_quality(True, io_bytes)

        element = common.IOElement_M_ME_TE(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_ME_TF:
        value, io_bytes = _decode_floating_value(io_bytes)
        quality, io_bytes = _decode_quality(True, io_bytes)

        element = common.IOElement_M_ME_TF(value=value,
                                           quality=quality)
        return element, io_bytes

    if asdu_type == common.AsduType.M_IT_TB:
        value, io_bytes = _decode_binary_counter_value(io_bytes)

        element = common.IOElement_M_IT_TB(value=value)
        return element, io_bytes

    if asdu_type == common.AsduType.C_SC_NA:
        value = common.SingleValue(io_bytes[0] & 1)
        select = bool(io_bytes[0] & 0x80)
        qualifier = (io_bytes[0] >> 2) & 0x1F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_SC_NA(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_DC_NA:
        value = common.DoubleValue(io_bytes[0] & 3)
        select = bool(io_bytes[0] & 0x80)
        qualifier = (io_bytes[0] >> 2) & 0x1F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_DC_NA(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_RC_NA:
        value = common.RegulatingValue(io_bytes[0] & 3)
        select = bool(io_bytes[0] & 0x80)
        qualifier = (io_bytes[0] >> 2) & 0x1F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_RC_NA(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_SE_NA:
        value, io_bytes = _decode_normalized_value(io_bytes)
        select = bool(io_bytes[0] & 0x80)
        qualifier = io_bytes[0] & 0x7F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_SE_NA(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_SE_NB:
        value, io_bytes = _decode_scaled_value(io_bytes)
        select = bool(io_bytes[0] & 0x80)
        qualifier = io_bytes[0] & 0x7F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_SE_NB(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_SE_NC:
        value, io_bytes = _decode_floating_value(io_bytes)
        select = bool(io_bytes[0] & 0x80)
        qualifier = io_bytes[0] & 0x7F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_SE_NC(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_SC_TA:
        value = common.SingleValue(io_bytes[0] & 1)
        select = bool(io_bytes[0] & 0x80)
        qualifier = (io_bytes[0] >> 2) & 0x1F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_SC_TA(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_DC_TA:
        value = common.DoubleValue(io_bytes[0] & 3)
        select = bool(io_bytes[0] & 0x80)
        qualifier = (io_bytes[0] >> 2) & 0x1F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_DC_TA(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_RC_TA:
        value = common.RegulatingValue(io_bytes[0] & 3)
        select = bool(io_bytes[0] & 0x80)
        qualifier = (io_bytes[0] >> 2) & 0x1F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_RC_TA(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_SE_TA:
        value, io_bytes = _decode_normalized_value(io_bytes)
        select = bool(io_bytes[0] & 0x80)
        qualifier = io_bytes[0] & 0x7F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_SE_TA(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_SE_TB:
        value, io_bytes = _decode_scaled_value(io_bytes)
        select = bool(io_bytes[0] & 0x80)
        qualifier = io_bytes[0] & 0x7F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_SE_TB(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_SE_TC:
        value, io_bytes = _decode_floating_value(io_bytes)
        select = bool(io_bytes[0] & 0x80)
        qualifier = io_bytes[0] & 0x7F
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_SE_TC(value=value,
                                           select=select,
                                           qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.M_EI_NA:
        param_change = bool(io_bytes[0] & 0x80)
        cause = io_bytes[0] & 0x7F
        io_bytes = io_bytes[1:]

        element = common.IOElement_M_EI_NA(param_change=param_change,
                                           cause=cause)
        return element, io_bytes

    if asdu_type == common.AsduType.C_IC_NA:
        qualifier = io_bytes[0]
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_IC_NA(qualifier=qualifier)
        return element, io_bytes

    if asdu_type == common.AsduType.C_CI_NA:
        request = io_bytes[0] & 0x3F
        freeze = common.FreezeCode(io_bytes[0] >> 6)
        io_bytes = io_bytes[1:]

        element = common.IOElement_C_CI_NA(request=request,
                                           freeze=freeze)
        return element, io_bytes

    raise ValueError('unsupported ASDU type')


def _encode_io_element(element):
    if isinstance(element, common.IOElement_M_SP_NA):
        quality = element.quality._replace(overflow=None)
        yield (element.value.value |
               util.first(_encode_quality(quality)))

    elif isinstance(element, common.IOElement_M_DP_NA):
        quality = element.quality._replace(overflow=None)
        yield (element.value.value |
               util.first(_encode_quality(quality)))

    elif isinstance(element, common.IOElement_M_ST_NA):
        yield from _encode_step_position_value(element.value)
        yield from _encode_quality(element.quality)

    elif isinstance(element, common.IOElement_M_BO_NA):
        yield from _encode_bitstring_value(element.value)
        yield from _encode_quality(element.quality)

    elif isinstance(element, common.IOElement_M_ME_NA):
        yield from _encode_normalized_value(element.value)
        yield from _encode_quality(element.quality)

    elif isinstance(element, common.IOElement_M_ME_NB):
        yield from _encode_scaled_value(element.value)
        yield from _encode_quality(element.quality)

    elif isinstance(element, common.IOElement_M_ME_NC):
        yield from _encode_floating_value(element.value)
        yield from _encode_quality(element.quality)

    elif isinstance(element, common.IOElement_M_IT_NA):
        yield from _encode_binary_counter_value(element.value)

    elif isinstance(element, common.IOElement_M_ME_ND):
        yield from _encode_normalized_value(element.value)

    elif isinstance(element, common.IOElement_M_SP_TB):
        quality = element.quality._replace(overflow=None)
        yield (element.value.value |
               util.first(_encode_quality(quality)))

    elif isinstance(element, common.IOElement_M_DP_TB):
        quality = element.quality._replace(overflow=None)
        yield (element.value.value |
               util.first(_encode_quality(quality)))

    elif isinstance(element, common.IOElement_M_ST_TB):
        yield from _encode_step_position_value(element.value)
        yield from _encode_quality(element.quality)

    elif isinstance(element, common.IOElement_M_BO_TB):
        yield from _encode_bitstring_value(element.value)
        yield from _encode_quality(element.quality)

    elif isinstance(element, common.IOElement_M_ME_TD):
        yield from _encode_normalized_value(element.value)
        yield from _encode_quality(element.quality)

    elif isinstance(element, common.IOElement_M_ME_TE):
        yield from _encode_scaled_value(element.value)
        yield from _encode_quality(element.quality)

    elif isinstance(element, common.IOElement_M_ME_TF):
        yield from _encode_floating_value(element.value)
        yield from _encode_quality(element.quality)

    elif isinstance(element, common.IOElement_M_IT_TB):
        yield from _encode_binary_counter_value(element.value)

    elif isinstance(element, common.IOElement_C_SC_NA):
        yield (element.value.value |
               (0x80 if element.select else 0) |
               ((element.qualifier & 0x1F) << 2))

    elif isinstance(element, common.IOElement_C_DC_NA):
        yield (element.value.value |
               (0x80 if element.select else 0) |
               ((element.qualifier & 0x1F) << 2))

    elif isinstance(element, common.IOElement_C_RC_NA):
        yield (element.value.value |
               (0x80 if element.select else 0) |
               ((element.qualifier & 0x1F) << 2))

    elif isinstance(element, common.IOElement_C_SE_NA):
        yield from _encode_normalized_value(element.value)
        yield ((0x80 if element.select else 0) |
               (element.qualifier & 0x7F))

    elif isinstance(element, common.IOElement_C_SE_NB):
        yield from _encode_scaled_value(element.value)
        yield ((0x80 if element.select else 0) |
               (element.qualifier & 0x7F))

    elif isinstance(element, common.IOElement_C_SE_NC):
        yield from _encode_floating_value(element.value)
        yield ((0x80 if element.select else 0) |
               (element.qualifier & 0x7F))

    elif isinstance(element, common.IOElement_C_SC_TA):
        yield (element.value.value |
               (0x80 if element.select else 0) |
               ((element.qualifier & 0x1F) << 2))

    elif isinstance(element, common.IOElement_C_DC_TA):
        yield (element.value.value |
               (0x80 if element.select else 0) |
               ((element.qualifier & 0x1F) << 2))

    elif isinstance(element, common.IOElement_C_RC_TA):
        yield (element.value.value |
               (0x80 if element.select else 0) |
               ((element.qualifier & 0x1F) << 2))

    elif isinstance(element, common.IOElement_C_SE_TA):
        yield from _encode_normalized_value(element.value)
        yield ((0x80 if element.select else 0) |
               (element.qualifier & 0x7F))

    elif isinstance(element, common.IOElement_C_SE_TB):
        yield from _encode_scaled_value(element.value)
        yield ((0x80 if element.select else 0) |
               (element.qualifier & 0x7F))

    elif isinstance(element, common.IOElement_C_SE_TC):
        yield from _encode_floating_value(element.value)
        yield ((0x80 if element.select else 0) |
               (element.qualifier & 0x7F))

    elif isinstance(element, common.IOElement_M_EI_NA):
        yield ((0x80 if element.param_change else 0) |
               (element.cause & 0x7F))

    elif isinstance(element, common.IOElement_C_IC_NA):
        yield element.qualifier & 0xFF

    elif isinstance(element, common.IOElement_C_CI_NA):
        yield ((element.freeze.value << 6) |
               (element.request & 0x3F))

    else:
        raise ValueError('unsupported IO element')


def _decode_time(io_bytes):
    milliseconds = (io_bytes[1] << 8) | io_bytes[0]
    invalid = bool(io_bytes[2] & 0x80)
    minutes = io_bytes[2] & 0x3F
    summer_time = bool(io_bytes[3] & 0x80)
    hours = io_bytes[3] & 0x1F
    day_of_week = io_bytes[4] >> 5
    day_of_month = io_bytes[4] & 0x1F
    months = io_bytes[5] & 0x0F
    years = io_bytes[6] & 0x7F

    time = common.Time(milliseconds=milliseconds,
                       invalid=invalid,
                       minutes=minutes,
                       summer_time=summer_time,
                       hours=hours,
                       day_of_week=day_of_week,
                       day_of_month=day_of_month,
                       months=months,
                       years=years)
    return time, io_bytes[7:]


def _encode_time(time):
    yield time.milliseconds & 0xFF
    yield (time.milliseconds >> 8) & 0xFF
    yield ((0x80 if time.invalid else 0) |
           (time.minutes & 0x3F))
    yield ((0x80 if time.summer_time else 0) |
           (time.hours & 0x1F))
    yield (((time.day_of_week & 0x07) << 5) |
           (time.day_of_month & 0x1F))
    yield time.months & 0x0F
    yield time.years & 0x7F


def _decode_quality(parse_overflow, io_bytes):
    invalid = bool(io_bytes[0] & 0x80)
    not_topical = bool(io_bytes[0] & 0x40)
    substituted = bool(io_bytes[0] & 0x20)
    blocked = bool(io_bytes[0] & 0x10)
    overflow = bool(io_bytes[0] & 0x01) if parse_overflow else False

    quality = common.Quality(invalid=invalid,
                             not_topical=not_topical,
                             substituted=substituted,
                             blocked=blocked,
                             overflow=overflow)
    return quality, io_bytes[1:]


def _encode_quality(quality):
    yield ((0x80 if quality.invalid else 0) |
           (0x40 if quality.not_topical else 0) |
           (0x20 if quality.substituted else 0) |
           (0x10 if quality.blocked else 0) |
           (0x01 if quality.overflow else 0))


def _decode_step_position_value(io_bytes):
    value = (((-1 << 7) if io_bytes[0] & 0x40 else 0) |
             (io_bytes[0] & 0x7F))
    transient = bool(io_bytes[0] & 0x80)

    step_position_value = common.StepPositionValue(value=value,
                                                   transient=transient)
    return step_position_value, io_bytes[1:]


def _encode_step_position_value(value):
    yield ((0x80 if value.transient else 0) |
           (value.value & 0x7F))


def _decode_bitstring_value(io_bytes):
    value = bytes(io_bytes[:4])

    bitstring_value = common.BitstringValue(value)
    return bitstring_value, io_bytes[4:]


def _encode_bitstring_value(value):
    yield value.value[0]
    yield value.value[1]
    yield value.value[2]
    yield value.value[3]


def _decode_normalized_value(io_bytes):
    value = struct.unpack('<h', bytes(io_bytes[:2]))[0] / 0x7fff

    normalized_value = common.NormalizedValue(value)
    return normalized_value, io_bytes[2:]


def _encode_normalized_value(value):
    yield from struct.pack('<h', round(value.value * 0x7fff))


def _decode_scaled_value(io_bytes):
    value = struct.unpack('<h', bytes(io_bytes[:2]))[0]

    scaled_value = common.ScaledValue(value)
    return scaled_value, io_bytes[2:]


def _encode_scaled_value(value):
    yield from struct.pack('<h', value.value)


def _decode_floating_value(io_bytes):
    value = struct.unpack('<f', bytes(io_bytes[:4]))[0]

    floating_value = common.FloatingValue(value)
    return floating_value, io_bytes[4:]


def _encode_floating_value(value):
    yield from struct.pack('<f', value.value)


def _decode_binary_counter_value(io_bytes):
    value = struct.unpack('<i', bytes(io_bytes[:4]))[0]
    invalid = bool(io_bytes[4] & 0x80)
    adjusted = bool(io_bytes[4] & 0x40)
    overflow = bool(io_bytes[4] & 0x20)
    sequence = io_bytes[4] & 0x1F

    binary_counter_value = common.BinaryCounterValue(value=value,
                                                     invalid=invalid,
                                                     adjusted=adjusted,
                                                     overflow=overflow,
                                                     sequence=sequence)
    return binary_counter_value, io_bytes[5:]


def _encode_binary_counter_value(value):
    yield from struct.pack('<i', value.value)
    yield ((0x80 if value.invalid else 0) |
           (0x40 if value.adjusted else 0) |
           (0x20 if value.overflow else 0) |
           (value.sequence & 0x1F))


_asdu_types_with_time = {common.AsduType.M_SP_TB,
                         common.AsduType.M_DP_TB,
                         common.AsduType.M_ST_TB,
                         common.AsduType.M_BO_TB,
                         common.AsduType.M_ME_TD,
                         common.AsduType.M_ME_TE,
                         common.AsduType.M_ME_TF,
                         common.AsduType.M_IT_TB,
                         common.AsduType.C_SC_TA,
                         common.AsduType.C_DC_TA,
                         common.AsduType.C_RC_TA,
                         common.AsduType.C_SE_TA,
                         common.AsduType.C_SE_TB,
                         common.AsduType.C_SE_TC}
