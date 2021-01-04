"""Modbus common data structures"""

import abc
import contextlib
import enum
import typing


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


class ReadReqPdu(typing.NamedTuple):
    data_type: DataType
    address: int
    quantity: typing.Optional[int]


class ReadResPdu(typing.NamedTuple):
    data_type: DataType
    values: typing.List[int]


class ReadErrPdu(typing.NamedTuple):
    data_type: DataType
    error: Error


class WriteSingleReqPdu(typing.NamedTuple):
    data_type: DataType
    address: int
    value: int


class WriteSingleResPdu(typing.NamedTuple):
    data_type: DataType
    address: int
    value: int


class WriteSingleErrPdu(typing.NamedTuple):
    data_type: DataType
    error: Error


class WriteMultipleReqPdu(typing.NamedTuple):
    data_type: DataType
    address: int
    values: typing.List[int]


class WriteMultipleResPdu(typing.NamedTuple):
    data_type: DataType
    address: int
    quantity: int


class WriteMultipleErrPdu(typing.NamedTuple):
    data_type: DataType
    error: Error


ReqPdu = type('ReqPdu', (abc.ABC, ), {})
ReqPdu.register(ReadReqPdu)
ReqPdu.register(WriteSingleReqPdu)
ReqPdu.register(WriteMultipleReqPdu)

ResPdu = type('ResPdu', (abc.ABC, ), {})
ResPdu.register(ReadResPdu)
ResPdu.register(WriteSingleResPdu)
ResPdu.register(WriteMultipleResPdu)

ErrPdu = type('ErrPdu', (abc.ABC, ), {})
ErrPdu.register(ReadErrPdu)
ErrPdu.register(WriteSingleErrPdu)
ErrPdu.register(WriteMultipleErrPdu)

Pdu = typing.Union[ReqPdu, ResPdu, ErrPdu]


class TcpAdu(typing.NamedTuple):
    transaction_id: int
    device_id: int
    pdu: Pdu


class RtuAdu(typing.NamedTuple):
    device_id: int
    pdu: Pdu


class AsciiAdu(typing.NamedTuple):
    device_id: int
    pdu: Pdu


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
