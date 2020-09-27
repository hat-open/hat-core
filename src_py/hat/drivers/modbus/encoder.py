"""Modbus encoder"""

import itertools
import struct

from hat.drivers.modbus import common


async def read_adu(modbus_type, direction, reader):
    if modbus_type == common.ModbusType.TCP:
        return await _read_adu_tcp(direction, reader)

    if modbus_type == common.ModbusType.RTU:
        return await _read_adu_rtu(direction, reader)

    if modbus_type == common.ModbusType.ASCII:
        return await _read_adu_ascii(direction, reader)

    raise ValueError("unsupported modbus type")


def encode_adu(adu):
    if isinstance(adu, common.TcpAdu):
        return _encode_adu_tcp(adu)

    if isinstance(adu, common.RtuAdu):
        return _encode_adu_rtu(adu)

    if isinstance(adu, common.AsciiAdu):
        return _encode_adu_ascii(adu)

    raise ValueError("unsupported modbus type")


def _encode_adu_tcp(adu):
    pdu_bytes = _encode_pdu(adu.pdu)
    header = struct.pack('>HHHB', adu.transaction_id, 0,  len(pdu_bytes) + 1,
                         adu.device_id)
    return bytes(itertools.chain(header, pdu_bytes))


def _encode_adu_rtu(adu):
    msg_bytes = bytearray([adu.device_id])
    msg_bytes.extend(_encode_pdu(adu.pdu))
    crc = _calculate_crc(msg_bytes)
    msg_bytes.extend([crc & 0xFF, crc >> 8])
    return bytes(msg_bytes)


def _encode_adu_ascii(adu):
    msg_bytes = bytearray([adu.device_id])
    msg_bytes.extend(_encode_pdu(adu.pdu))
    lrc = _calculate_lrc(msg_bytes)
    msg_bytes.extend([lrc])
    msg_ascii = bytearray(b':')
    for i in msg_bytes:
        msg_ascii.extend(f'{i:02X}'.encode('ascii'))
    msg_ascii.extend(b'\r\n')
    return bytes(msg_ascii)


def _encode_pdu(pdu):
    if isinstance(pdu, common.ReqPdu):
        return _encode_pdu_req(pdu)

    if isinstance(pdu, common.ResPdu):
        return _encode_pdu_res(pdu)

    if isinstance(pdu, common.ErrPdu):
        return _encode_pdu_err(pdu)

    raise ValueError("invalid pdu")


def _encode_pdu_req(pdu):
    if isinstance(pdu, common.ReadReqPdu):
        return _encode_pdu_req_read(pdu)

    if isinstance(pdu, common.WriteSingleReqPdu):
        return _encode_pdu_req_write_single(pdu)

    if isinstance(pdu, common.WriteMultipleReqPdu):
        return _encode_pdu_req_write_multiple(pdu)

    raise ValueError("invalid pdu")


def _encode_pdu_res(pdu):
    if isinstance(pdu, common.ReadResPdu):
        return _encode_pdu_res_read(pdu)

    if isinstance(pdu, common.WriteSingleResPdu):
        return _encode_pdu_res_write_single(pdu)

    if isinstance(pdu, common.WriteMultipleResPdu):
        return _encode_pdu_res_write_multiple(pdu)

    raise ValueError("invalid pdu")


def _encode_pdu_err(pdu):
    if isinstance(pdu, common.ReadErrPdu):
        return _encode_pdu_err_read(pdu)

    if isinstance(pdu, common.WriteSingleErrPdu):
        return _encode_pdu_err_write_single(pdu)

    if isinstance(pdu, common.WriteMultipleErrPdu):
        return _encode_pdu_err_write_multiple(pdu)

    raise ValueError("invalid pdu")


def _encode_pdu_req_read(pdu):
    if pdu.data_type == common.DataType.COIL:
        fc = 1
        data = struct.pack('>HH', pdu.address, pdu.quantity)

    elif pdu.data_type == common.DataType.DISCRETE_INPUT:
        fc = 2
        data = struct.pack('>HH', pdu.address, pdu.quantity)

    elif pdu.data_type == common.DataType.HOLDING_REGISTER:
        fc = 3
        data = struct.pack('>HH', pdu.address, pdu.quantity)

    elif pdu.data_type == common.DataType.INPUT_REGISTER:
        fc = 4
        data = struct.pack('>HH', pdu.address, pdu.quantity)

    elif pdu.data_type == common.DataType.QUEUE:
        fc = 24
        data = struct.pack('>H', pdu.address)

    else:
        raise ValueError("unsupported data type")

    return bytes([fc, *data])


def _encode_pdu_req_write_single(pdu):
    if pdu.data_type == common.DataType.COIL:
        fc = 5
        data = struct.pack('>HH', pdu.address, 0xFF00 if pdu.value else 0)

    elif pdu.data_type == common.DataType.HOLDING_REGISTER:
        fc = 6
        data = struct.pack('>HH', pdu.address, pdu.value)

    else:
        raise ValueError("unsupported data type")

    return bytes([fc, *data])


def _encode_pdu_req_write_multiple(pdu):
    if pdu.data_type == common.DataType.COIL:
        fc = 15
        quantity = len(pdu.values)
        count = quantity // 8 + (1 if quantity % 8 else 0)
        data = bytearray(struct.pack('>HHB', pdu.address, quantity, count))
        for i in range(count):
            data_byte = 0
            for j in range(8):
                if len(pdu.values) > i * 8 + j and pdu.values[i * 8 + j]:
                    data_byte = data_byte | (1 << j)
            data.append(data_byte)

    elif pdu.data_type == common.DataType.HOLDING_REGISTER:
        fc = 16
        quantity = len(pdu.values)
        count = 2 * quantity
        data = bytearray(struct.pack('>HHB', pdu.address, quantity, count))
        for i in range(count):
            data.append((pdu.values[i // 2] >> (0 if i % 2 else 8)) & 0xFF)

    else:
        raise ValueError("unsupported data type")

    return bytes([fc, *data])


def _encode_pdu_res_read(pdu):
    if pdu.data_type == common.DataType.COIL:
        fc = 1
        quantity = len(pdu.values)
        count = quantity // 8 + (1 if quantity % 8 else 0)
        data = bytearray([count])
        for i in range(count):
            data_byte = 0
            for j in range(8):
                if len(pdu.values) > i * 8 + j and pdu.values[i * 8 + j]:
                    data_byte = data_byte | (1 << j)
            data.append(data_byte)

    elif pdu.data_type == common.DataType.DISCRETE_INPUT:
        fc = 2
        quantity = len(pdu.values)
        count = quantity // 8 + (1 if quantity % 8 else 0)
        data = bytearray([count])
        for i in range(count):
            data_byte = 0
            for j in range(8):
                if len(pdu.values) > i * 8 + j and pdu.values[i * 8 + j]:
                    data_byte = data_byte | (1 << j)
            data.append(data_byte)

    elif pdu.data_type == common.DataType.HOLDING_REGISTER:
        fc = 3
        data = bytearray([len(pdu.values) * 2])
        for i in pdu.values:
            data.extend([(i >> 8) & 0xFF, i & 0xFF])

    elif pdu.data_type == common.DataType.INPUT_REGISTER:
        fc = 4
        data = bytearray([len(pdu.values) * 2])
        for i in pdu.values:
            data.extend([(i >> 8) & 0xFF, i & 0xFF])

    elif pdu.data_type == common.DataType.QUEUE:
        fc = 24
        data = bytearray([len(pdu.values) * 2])
        for i in pdu.values:
            data.extend([(i >> 8) & 0xFF, i & 0xFF])

    else:
        raise ValueError("unsupported data type")

    return bytes([fc, *data])


def _encode_pdu_res_write_single(pdu):
    if pdu.data_type == common.DataType.COIL:
        fc = 5
        data = struct.pack('>HH', pdu.address, 0xFF00 if pdu.value else 0)

    elif pdu.data_type == common.DataType.HOLDING_REGISTER:
        fc = 6
        data = struct.pack('>HH', pdu.address, pdu.value)

    else:
        raise ValueError("unsupported data type")

    return bytes([fc, *data])


def _encode_pdu_res_write_multiple(pdu):
    if pdu.data_type == common.DataType.COIL:
        fc = 15
        data = struct.pack('>HH', pdu.address, pdu.quantity)

    elif pdu.data_type == common.DataType.HOLDING_REGISTER:
        fc = 16
        data = struct.pack('>HH', pdu.address, pdu.quantity)

    else:
        raise ValueError("unsupported data type")

    return bytes([fc, *data])


def _encode_pdu_err_read(pdu):
    if pdu.data_type == common.DataType.COIL:
        fc = 1

    elif pdu.data_type == common.DataType.DISCRETE_INPUT:
        fc = 2

    elif pdu.data_type == common.DataType.HOLDING_REGISTER:
        fc = 3

    elif pdu.data_type == common.DataType.INPUT_REGISTER:
        fc = 4

    elif pdu.data_type == common.DataType.QUEUE:
        fc = 24

    else:
        raise ValueError("unsupported data type")

    return bytes([0x80 | fc, pdu.error.value])


def _encode_pdu_err_write_single(pdu):
    if pdu.data_type == common.DataType.COIL:
        fc = 5

    elif pdu.data_type == common.DataType.HOLDING_REGISTER:
        fc = 6

    else:
        raise ValueError("unsupported data type")

    return bytes([0x80 | fc, pdu.error.value])


def _encode_pdu_err_write_multiple(pdu):
    if pdu.data_type == common.DataType.COIL:
        fc = 15

    elif pdu.data_type == common.DataType.HOLDING_REGISTER:
        fc = 16

    else:
        raise ValueError("unsupported data type")

    return bytes([0x80 | fc, pdu.error.value])


async def _read_adu_tcp(direction, reader):
    mbap_bytes = await reader.read(7)
    transaction_id, identifier, length, device_id = struct.unpack(
        '>HHHB', mbap_bytes)
    if identifier:
        raise Exception('Invalid protocol identifier')
    data = await reader.read(length - 1)
    memory_reader = common.MemoryReader(data)
    pdu = await _read_pdu(direction, memory_reader)
    return common.TcpAdu(transaction_id=transaction_id,
                         device_id=device_id,
                         pdu=pdu)


async def _read_adu_rtu(direction, reader):
    caching_reader = common.CachingReader(reader)
    device_id = (await caching_reader.read(1))[0]
    pdu = await _read_pdu(direction, caching_reader)
    crc = _calculate_crc(caching_reader.cache)
    crc_bytes = await reader.read(2)
    if (crc_bytes[1] << 8) | crc_bytes[0] != crc:
        raise Exception("CRC didn't match received message")
    return common.RtuAdu(device_id=device_id, pdu=pdu)


async def _read_adu_ascii(direction, reader):
    while b':' != await reader.read(1):
        pass
    data = bytearray()
    while True:
        temp = await reader.read(2)
        if temp == b'\r\n':
            break
        data.append(int(temp, 16))
    memory_reader = common.MemoryReader(data)
    caching_reader = common.CachingReader(memory_reader)
    device_id = (await caching_reader.read(1))[0]
    pdu = await _read_pdu(direction, caching_reader)
    lrc = _calculate_lrc(caching_reader.cache)
    if lrc != (await caching_reader.read(1))[0]:
        raise Exception("LRC didn't match received message")
    return common.AsciiAdu(device_id=device_id, pdu=pdu)


async def _read_pdu(direction, reader):
    if direction == common.Direction.REQUEST:
        return await _read_pdu_req(reader)

    if direction == common.Direction.RESPONSE:
        return await _read_pdu_res(reader)

    raise ValueError('invalid direction')


async def _read_pdu_req(reader):
    fc = (await reader.read(1))[0]

    if fc == 1:
        data_type = common.DataType.COIL
        address, quantity = struct.unpack('>HH', await reader.read(4))
        return common.ReadReqPdu(data_type=data_type,
                                 address=address,
                                 quantity=quantity)

    if fc == 2:
        data_type = common.DataType.DISCRETE_INPUT
        address, quantity = struct.unpack('>HH', await reader.read(4))
        return common.ReadReqPdu(data_type=data_type,
                                 address=address,
                                 quantity=quantity)

    if fc == 3:
        data_type = common.DataType.HOLDING_REGISTER
        address, quantity = struct.unpack('>HH', await reader.read(4))
        return common.ReadReqPdu(data_type=data_type,
                                 address=address,
                                 quantity=quantity)

    if fc == 4:
        data_type = common.DataType.INPUT_REGISTER
        address, quantity = struct.unpack('>HH', await reader.read(4))
        return common.ReadReqPdu(data_type=data_type,
                                 address=address,
                                 quantity=quantity)

    if fc == 5:
        data_type = common.DataType.COIL
        address, value = struct.unpack('>HH', await reader.read(4))
        return common.WriteSingleReqPdu(data_type=data_type,
                                        address=address,
                                        value=bool(value))

    if fc == 6:
        data_type = common.DataType.HOLDING_REGISTER
        address, value = struct.unpack('>HH', await reader.read(4))
        return common.WriteSingleReqPdu(data_type=data_type,
                                        address=address,
                                        value=value)

    if fc == 15:
        data_type = common.DataType.COIL
        address, quantity, byte_count = struct.unpack('>HHB',
                                                      await reader.read(5))
        values_bytes = await reader.read(byte_count)
        values = [int(bool(values_bytes[i // 8] & (1 << (i % 8))))
                  for i in range(quantity)]
        return common.WriteMultipleReqPdu(data_type=data_type,
                                          address=address,
                                          values=values)

    if fc == 16:
        data_type = common.DataType.HOLDING_REGISTER
        address, quantity, byte_count = struct.unpack('>HHB',
                                                      await reader.read(5))
        values_bytes = await reader.read(byte_count)
        values = [(values_bytes[i * 2] << 8) | values_bytes[i * 2 + 1]
                  for i in range(quantity)]
        return common.WriteMultipleReqPdu(data_type=data_type,
                                          address=address,
                                          values=values)

    if fc == 24:
        data_type = common.DataType.QUEUE
        address = struct.unpack('>H', await reader.read(2))[0]
        return common.ReadReqPdu(data_type=data_type,
                                 address=address,
                                 quantity=None)

    raise Exception("unsupported function code %s", fc)


async def _read_pdu_res(reader):
    fc = (await reader.read(1))[0]
    is_err, fc = bool(fc & 0x80), (fc & 0x7F)
    error = common.Error((await reader.read(1))[0]) if is_err else None

    if fc == 1:
        data_type = common.DataType.COIL
        if error:
            return common.ReadErrPdu(data_type, error)
        byte_count = (await reader.read(1))[0]
        data = await reader.read(byte_count)
        values = list(itertools.chain.from_iterable(((i >> j) & 1
                                                     for j in range(8))
                                                    for i in data))
        return common.ReadResPdu(data_type=data_type,
                                 values=values)

    if fc == 2:
        data_type = common.DataType.DISCRETE_INPUT
        if error:
            return common.ReadErrPdu(data_type, error)
        byte_count = (await reader.read(1))[0]
        data = await reader.read(byte_count)
        values = list(itertools.chain.from_iterable(((i >> j) & 1
                                                     for j in range(8))
                                                    for i in data))
        return common.ReadResPdu(data_type=data_type,
                                 values=values)

    if fc == 3:
        data_type = common.DataType.HOLDING_REGISTER
        if error:
            return common.ReadErrPdu(data_type, error)
        byte_count = (await reader.read(1))[0]
        if byte_count % 2:
            raise Exception('invalid number of bytes')
        data = await reader.read(byte_count)
        values = [(data[i * 2] << 8) | data[1 + i * 2]
                  for i in range(byte_count // 2)]
        return common.ReadResPdu(data_type=data_type,
                                 values=values)

    if fc == 4:
        data_type = common.DataType.INPUT_REGISTER
        if error:
            return common.ReadErrPdu(data_type, error)
        byte_count = (await reader.read(1))[0]
        if byte_count % 2:
            raise Exception('invalid number of bytes')
        data = await reader.read(byte_count)
        values = [(data[i * 2] << 8) | data[1 + i * 2]
                  for i in range(byte_count // 2)]
        return common.ReadResPdu(data_type=data_type,
                                 values=values)

    if fc == 5:
        data_type = common.DataType.COIL
        if error:
            return common.WriteSingleErrPdu(data_type, error)
        data = await reader.read(4)
        address = (data[0] << 8) | data[1]
        value = int(bool((data[2] << 8) | data[3]))
        return common.WriteSingleResPdu(data_type=data_type,
                                        address=address,
                                        value=value)

    if fc == 6:
        data_type = common.DataType.HOLDING_REGISTER
        if error:
            return common.WriteSingleErrPdu(data_type, error)
        data = await reader.read(4)
        address = (data[0] << 8) | data[1]
        value = (data[2] << 8) | data[3]
        return common.WriteSingleResPdu(data_type=data_type,
                                        address=address,
                                        value=value)

    if fc == 15:
        data_type = common.DataType.COIL
        if error:
            return common.WriteMultipleErrPdu(data_type, error)
        data = await reader.read(4)
        address = (data[0] << 8) | data[1]
        quantity = (data[2] << 8) | data[3]
        return common.WriteMultipleResPdu(data_type=data_type,
                                          address=address,
                                          quantity=quantity)

    if fc == 16:
        data_type = common.DataType.HOLDING_REGISTER
        if error:
            return common.WriteMultipleErrPdu(data_type, error)
        data = await reader.read(4)
        address = (data[0] << 8) | data[1]
        quantity = (data[2] << 8) | data[3]
        return common.WriteMultipleResPdu(data_type=data_type,
                                          address=address,
                                          quantity=quantity)

    if fc == 24:
        data_type = common.DataType.QUEUE
        if error:
            return common.ReadErrPdu(data_type, error)
        byte_count = (await reader.read(1))[0]
        if byte_count % 2:
            raise Exception('invalid number of bytes')
        data = await reader.read(byte_count)
        values = [(data[i * 2] << 8) | data[1 + i * 2]
                  for i in range(byte_count // 2)]
        return common.ReadResPdu(data_type=data_type,
                                 values=values)

    raise Exception("unsupported function code %s", fc)


def _calculate_crc(data):
    crc = 0xFFFF
    for i in data:
        crc ^= i
        for _ in range(8):
            lsb = crc & 1
            crc >>= 1
            if lsb:
                crc ^= 0xA001
    return crc


def _calculate_lrc(data):
    return (~sum(data) + 1) & 0xFF
