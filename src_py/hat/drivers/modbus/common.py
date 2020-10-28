"""Modbus common data structures"""

import abc
import contextlib
import enum
import typing

from hat import util


class DataType(enum.Enum):
    COIL = 1
    DISCRETE_INPUT = 2
    HOLDING_REGISTER = 3
    INPUT_REGISTER = 4
    QUEUE = 5


class Error(enum.Enum):
    INVALID_FUNCTION_CODE = 1
    INVALID_DATA_ADDRESS = 2
    INVALID_DATA_VALUE = 3
    FUNCTION_ERROR = 4


class ModbusType(enum.Enum):
    TCP = 0
    RTU = 1
    ASCII = 2


class Direction(enum.Enum):
    REQUEST = 0
    RESPONSE = 1


class ReqPdu(abc.ABC):
    pass


class ResPdu(abc.ABC):
    pass


class ErrPdu(abc.ABC):
    pass


ReadReqPdu = util.namedtuple(
    'ReadReqPdu',
    ['data_type', 'DataType'],
    ['address', 'int'],
    ['quantity', 'Optional[int]'])
ReqPdu.register(ReadReqPdu)


ReadResPdu = util.namedtuple(
    'ReadResPdu',
    ['data_type', 'DataType'],
    ['values', 'List[int]'])
ResPdu.register(ReadResPdu)


ReadErrPdu = util.namedtuple(
    'ReadErrPdu',
    ['data_type', 'DataType'],
    ['error', 'Error'])
ErrPdu.register(ReadErrPdu)


WriteSingleReqPdu = util.namedtuple(
    'WriteSingleReqPdu',
    ['data_type', 'DataType'],
    ['address', 'int'],
    ['value', 'int'])
ReqPdu.register(WriteSingleReqPdu)


WriteSingleResPdu = util.namedtuple(
    'WriteSingleResPdu',
    ['data_type', 'DataType'],
    ['address', 'int'],
    ['value', 'int'])
ResPdu.register(WriteSingleResPdu)


WriteSingleErrPdu = util.namedtuple(
    'WriteSingleErrPdu',
    ['data_type', 'DataType'],
    ['error', 'Error'])
ErrPdu.register(WriteSingleErrPdu)


WriteMultipleReqPdu = util.namedtuple(
    'WriteMultipleReqPdu',
    ['data_type', 'DataType'],
    ['address', 'int'],
    ['values', 'List[int]'])
ReqPdu.register(WriteMultipleReqPdu)


WriteMultipleResPdu = util.namedtuple(
    'WriteMultipleResPdu',
    ['data_type', 'DataType'],
    ['address', 'int'],
    ['quantity', 'int'])
ResPdu.register(WriteMultipleResPdu)


WriteMultipleErrPdu = util.namedtuple(
    'WriteMultipleErrPdu',
    ['data_type', 'DataType'],
    ['error', 'Error'])
ErrPdu.register(WriteMultipleErrPdu)


Pdu = typing.Union[ReqPdu, ResPdu, ErrPdu]


TcpAdu = util.namedtuple(
    'TcpAdu',
    ['transaction_id', 'int'],
    ['device_id', 'int'],
    ['pdu', 'Pdu'])


RtuAdu = util.namedtuple(
    'RtuAdu',
    ['device_id', 'int'],
    ['pdu', 'Pdu'])


AsciiAdu = util.namedtuple(
    'AsciiAdu',
    ['device_id', 'int'],
    ['pdu', 'Pdu'])


Adu = typing.Union[TcpAdu, RtuAdu, AsciiAdu]


class TcpWriter:

    def __init__(self, writer):
        self._writer = writer

    async def write(self, data):
        self._writer.write(data)
        await self._writer.drain()

    async def async_close(self):
        with contextlib.suppress(Exception):
            self._writer.close()
        with contextlib.suppress(ConnectionError):
            await self._writer.wait_closed()


class SerialWriter:

    def __init__(self, conn):
        self._conn = conn

    async def write(self, data):
        await self._conn.write(data)

    async def async_close(self):
        await self._conn.async_close()


class TcpReader:

    def __init__(self, reader):
        self._reader = reader

    async def read(self, size):
        return await self._reader.readexactly(size)


class SerialReader:

    def __init__(self, conn):
        self._conn = conn

    async def read(self, size):
        data = await self._conn.read(size)
        if len(data) < size:
            raise EOFError()
        return data


class MemoryReader:

    def __init__(self, data):
        self._data = memoryview(data)

    async def read(self, size):
        if len(self._data) < size:
            raise EOFError()
        data, self._data = self._data[:size], self._data[size:]
        return data


class CachingReader:

    def __init__(self, reader):
        self._reader = reader
        self._cache = bytearray()

    @property
    def cache(self):
        return self._cache

    async def read(self, size):
        data = await self._reader.read(size)
        self._cache.extend(data)
        return data
