"""Modbus encoder"""

import enum
import itertools
import struct

from hat.drivers.modbus import common
from hat.drivers.modbus import messages
from hat.drivers.modbus import transport


class Direction(enum.Enum):
    REQUEST = 0
    RESPONSE = 1


async def read_adu(modbus_type: common.ModbusType,
                   direction: Direction,
                   reader: transport.Reader
                   ) -> messages.Adu:
    if modbus_type == common.ModbusType.TCP:
        return await _read_adu_tcp(direction, reader)

    if modbus_type == common.ModbusType.RTU:
        return await _read_adu_rtu(direction, reader)

    if modbus_type == common.ModbusType.ASCII:
        return await _read_adu_ascii(direction, reader)

    raise ValueError("unsupported modbus type")


def encode_adu(adu: messages.Adu) -> transport.Data:
    if isinstance(adu, messages.TcpAdu):
        return _encode_adu_tcp(adu)

    if isinstance(adu, messages.RtuAdu):
        return _encode_adu_rtu(adu)

    if isinstance(adu, messages.AsciiAdu):
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
    if isinstance(pdu.data, messages.Request):
        fc = pdu.fc.value
        data = _encode_req(pdu.data)

    elif isinstance(pdu.data, messages.Response):
        fc = pdu.fc.value
        data = _encode_res(pdu.data)

    elif isinstance(pdu.data, common.Error):
        fc = pdu.fc.value + 0x80
        data = [pdu.data.value]

    else:
        raise ValueError('unsupported pdu data')

    return bytes([fc, *data])


def _encode_req(req):
    if isinstance(req, messages.ReadCoilsReq):
        return struct.pack('>HH', req.address, req.quantity)

    if isinstance(req, messages.ReadDiscreteInputsReq):
        return struct.pack('>HH', req.address, req.quantity)

    if isinstance(req, messages.ReadHoldingRegistersReq):
        return struct.pack('>HH', req.address, req.quantity)

    if isinstance(req, messages.ReadInputRegistersReq):
        return struct.pack('>HH', req.address, req.quantity)

    if isinstance(req, messages.WriteSingleCoilReq):
        return struct.pack('>HH', req.address, 0xFF00 if req.value else 0)

    if isinstance(req, messages.WriteSingleRegisterReq):
        return struct.pack('>HH', req.address, req.value)

    if isinstance(req, messages.WriteMultipleCoilsReq):
        quantity = len(req.values)
        count = quantity // 8 + (1 if quantity % 8 else 0)
        data = bytearray(struct.pack('>HHB', req.address, quantity, count))
        for i in range(count):
            data_byte = 0
            for j in range(8):
                if len(req.values) > i * 8 + j and req.values[i * 8 + j]:
                    data_byte = data_byte | (1 << j)
            data.append(data_byte)
        return data

    if isinstance(req, messages.WriteMultipleRegistersReq):
        quantity = len(req.values)
        count = 2 * quantity
        data = bytearray(struct.pack('>HHB', req.address, quantity, count))
        for i in range(count):
            data.append((req.values[i // 2] >> (0 if i % 2 else 8)) & 0xFF)
        return data

    if isinstance(req, messages.MaskWriteRegisterReq):
        return struct.pack('>HHH', req.address, req.and_mask, req.or_mask)

    if isinstance(req, messages.ReadFifoQueueReq):
        return struct.pack('>H', req.address)

    raise ValueError('unsupported request type')


def _encode_res(res):
    if isinstance(res, messages.ReadCoilsRes):
        quantity = len(res.values)
        count = quantity // 8 + (1 if quantity % 8 else 0)
        data = bytearray([count])
        for i in range(count):
            data_byte = 0
            for j in range(8):
                if (len(res.values) > i * 8 + j and
                        res.values[i * 8 + j]):
                    data_byte = data_byte | (1 << j)
            data.append(data_byte)
        return data

    if isinstance(res, messages.ReadDiscreteInputsRes):
        quantity = len(res.values)
        count = quantity // 8 + (1 if quantity % 8 else 0)
        data = bytearray([count])
        for i in range(count):
            data_byte = 0
            for j in range(8):
                if len(res.values) > i * 8 + j and res.values[i * 8 + j]:
                    data_byte = data_byte | (1 << j)
            data.append(data_byte)
        return data

    if isinstance(res, messages.ReadHoldingRegistersRes):
        data = bytearray([len(res.values) * 2])
        for i in res.values:
            data.extend([(i >> 8) & 0xFF, i & 0xFF])
        return data

    if isinstance(res, messages.ReadInputRegistersRes):
        data = bytearray([len(res.values) * 2])
        for i in res.values:
            data.extend([(i >> 8) & 0xFF, i & 0xFF])
        return data

    if isinstance(res, messages.WriteSingleCoilRes):
        return struct.pack('>HH', res.address, 0xFF00 if res.value else 0)

    if isinstance(res, messages.WriteSingleRegisterRes):
        return struct.pack('>HH', res.address, res.value)

    if isinstance(res, messages.WriteMultipleCoilsRes):
        return struct.pack('>HH', res.address, res.quantity)

    if isinstance(res, messages.WriteMultipleRegistersRes):
        return struct.pack('>HH', res.address, res.quantity)

    if isinstance(res, messages.MaskWriteRegisterRes):
        return struct.pack('>HHH', res.address, res.and_mask, res.or_mask)

    if isinstance(res, messages.ReadFifoQueueRes):
        data = bytearray([len(res.values) * 2])
        for i in res.values:
            data.extend([(i >> 8) & 0xFF, i & 0xFF])
        return data

    raise ValueError('unsupported request type')


async def _read_adu_tcp(direction, reader):
    mbap_bytes = await reader.read(7)
    transaction_id, identifier, length, device_id = struct.unpack(
        '>HHHB', mbap_bytes)
    if identifier:
        raise Exception('Invalid protocol identifier')
    data = await reader.read(length - 1)
    memory_reader = transport.MemoryReader(data)
    pdu = await _read_pdu(direction, memory_reader)
    return messages.TcpAdu(transaction_id=transaction_id,
                           device_id=device_id,
                           pdu=pdu)


async def _read_adu_rtu(direction, reader):
    caching_reader = transport.CachingReader(reader)
    device_id = (await caching_reader.read(1))[0]
    pdu = await _read_pdu(direction, caching_reader)
    crc = _calculate_crc(caching_reader.cache)
    crc_bytes = await reader.read(2)
    if (crc_bytes[1] << 8) | crc_bytes[0] != crc:
        raise Exception("CRC didn't match received message")
    return messages.RtuAdu(device_id=device_id, pdu=pdu)


async def _read_adu_ascii(direction, reader):
    while b':' != await reader.read(1):
        pass
    data = bytearray()
    while True:
        temp = await reader.read(2)
        if temp == b'\r\n':
            break
        data.append(int(temp, 16))
    memory_reader = transport.MemoryReader(data)
    caching_reader = transport.CachingReader(memory_reader)
    device_id = (await caching_reader.read(1))[0]
    pdu = await _read_pdu(direction, caching_reader)
    lrc = _calculate_lrc(caching_reader.cache)
    if lrc != (await caching_reader.read(1))[0]:
        raise Exception("LRC didn't match received message")
    return messages.AsciiAdu(device_id=device_id, pdu=pdu)


async def _read_pdu(direction, reader):
    fc = (await reader.read(1))[0]

    if direction == Direction.REQUEST:
        fc = messages.FunctionCode(fc)
        data = await _read_req(fc, reader)

    elif direction == Direction.RESPONSE:
        if fc & 0x80:
            fc = messages.FunctionCode(fc & 0x7F)
            data = common.Error((await reader.read(1))[0])
        else:
            fc = messages.FunctionCode(fc)
            data = await _read_res(fc, reader)

    else:
        raise ValueError('invalid direction')

    return messages.Pdu(fc=fc, data=data)


async def _read_req(fc, reader):
    if fc == messages.FunctionCode.READ_COILS:
        address, quantity = struct.unpack('>HH', await reader.read(4))
        return messages.ReadCoilsReq(address=address,
                                     quantity=quantity)

    if fc == messages.FunctionCode.READ_DISCRETE_INPUTS:
        address, quantity = struct.unpack('>HH', await reader.read(4))
        return messages.ReadDiscreteInputsReq(address=address,
                                              quantity=quantity)

    if fc == messages.FunctionCode.READ_HOLDING_REGISTERS:
        address, quantity = struct.unpack('>HH', await reader.read(4))
        return messages.ReadHoldingRegistersReq(address=address,
                                                quantity=quantity)

    if fc == messages.FunctionCode.READ_INPUT_REGISTERS:
        address, quantity = struct.unpack('>HH', await reader.read(4))
        return messages.ReadInputRegistersReq(address=address,
                                              quantity=quantity)

    if fc == messages.FunctionCode.WRITE_SINGLE_COIL:
        address, value = struct.unpack('>HH', await reader.read(4))
        return messages.WriteSingleCoilReq(address=address,
                                           value=bool(value))

    if fc == messages.FunctionCode.WRITE_SINGLE_REGISTER:
        address, value = struct.unpack('>HH', await reader.read(4))
        return messages.WriteSingleRegisterReq(address=address,
                                               value=value)

    if fc == messages.FunctionCode.WRITE_MULTIPLE_COILS:
        address, quantity, byte_count = struct.unpack('>HHB',
                                                      await reader.read(5))
        values_bytes = await reader.read(byte_count)
        values = [int(bool(values_bytes[i // 8] & (1 << (i % 8))))
                  for i in range(quantity)]
        return messages.WriteMultipleCoilsReq(address=address,
                                              values=values)

    if fc == messages.FunctionCode.WRITE_MULTIPLE_REGISTER:
        address, quantity, byte_count = struct.unpack('>HHB',
                                                      await reader.read(5))
        values_bytes = await reader.read(byte_count)
        values = [(values_bytes[i * 2] << 8) | values_bytes[i * 2 + 1]
                  for i in range(quantity)]
        return messages.WriteMultipleRegistersReq(address=address,
                                                  values=values)

    if fc == messages.FunctionCode.MASK_WRITE_REGISTER:
        address, and_mask, or_mask = struct.unpack('>HHH',
                                                   await reader.read(6))
        return messages.MaskWriteRegisterReq(address=address,
                                             and_mask=and_mask,
                                             or_mask=or_mask)

    if fc == messages.FunctionCode.READ_FIFO_QUEUE:
        address = struct.unpack('>H', await reader.read(2))[0]
        return messages.ReadFifoQueueReq(address=address)

    raise ValueError("unsupported function code")


async def _read_res(fc, reader):
    if fc == messages.FunctionCode.READ_COILS:
        byte_count = (await reader.read(1))[0]
        data = await reader.read(byte_count)
        values = list(itertools.chain.from_iterable(((i >> j) & 1
                                                     for j in range(8))
                                                    for i in data))
        return messages.ReadCoilsRes(values=values)

    if fc == messages.FunctionCode.READ_DISCRETE_INPUTS:
        byte_count = (await reader.read(1))[0]
        data = await reader.read(byte_count)
        values = list(itertools.chain.from_iterable(((i >> j) & 1
                                                     for j in range(8))
                                                    for i in data))
        return messages.ReadDiscreteInputsRes(values=values)

    if fc == messages.FunctionCode.READ_HOLDING_REGISTERS:
        byte_count = (await reader.read(1))[0]
        if byte_count % 2:
            raise Exception('invalid number of bytes')
        data = await reader.read(byte_count)
        values = [(data[i * 2] << 8) | data[1 + i * 2]
                  for i in range(byte_count // 2)]
        return messages.ReadHoldingRegistersRes(values=values)

    if fc == messages.FunctionCode.READ_INPUT_REGISTERS:
        byte_count = (await reader.read(1))[0]
        if byte_count % 2:
            raise Exception('invalid number of bytes')
        data = await reader.read(byte_count)
        values = [(data[i * 2] << 8) | data[1 + i * 2]
                  for i in range(byte_count // 2)]
        return messages.ReadInputRegistersRes(values=values)

    if fc == messages.FunctionCode.WRITE_SINGLE_COIL:
        data = await reader.read(4)
        address = (data[0] << 8) | data[1]
        value = int(bool((data[2] << 8) | data[3]))
        return messages.WriteSingleCoilRes(address=address,
                                           value=value)

    if fc == messages.FunctionCode.WRITE_SINGLE_REGISTER:
        data = await reader.read(4)
        address = (data[0] << 8) | data[1]
        value = (data[2] << 8) | data[3]
        return messages.WriteSingleRegisterRes(address=address,
                                               value=value)

    if fc == messages.FunctionCode.WRITE_MULTIPLE_COILS:
        data = await reader.read(4)
        address = (data[0] << 8) | data[1]
        quantity = (data[2] << 8) | data[3]
        return messages.WriteMultipleCoilsRes(address=address,
                                              quantity=quantity)

    if fc == messages.FunctionCode.WRITE_MULTIPLE_REGISTER:
        data = await reader.read(4)
        address = (data[0] << 8) | data[1]
        quantity = (data[2] << 8) | data[3]
        return messages.WriteMultipleRegistersRes(address=address,
                                                  quantity=quantity)

    if fc == messages.FunctionCode.MASK_WRITE_REGISTER:
        address, and_mask, or_mask = struct.unpack('>HHH',
                                                   await reader.read(6))
        return messages.MaskWriteRegisterRes(address=address,
                                             and_mask=and_mask,
                                             or_mask=or_mask)

    if fc == messages.FunctionCode.READ_FIFO_QUEUE:
        byte_count = (await reader.read(1))[0]
        if byte_count % 2:
            raise Exception('invalid number of bytes')
        data = await reader.read(byte_count)
        values = [(data[i * 2] << 8) | data[1 + i * 2]
                  for i in range(byte_count // 2)]
        return messages.ReadFifoQueueRes(values=values)

    raise ValueError("unsupported function code")


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
