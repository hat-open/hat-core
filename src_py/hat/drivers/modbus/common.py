"""Modbus common data structures"""

import abc
import enum
import typing


class ModbusType(enum.Enum):
    TCP = 0
    RTU = 1
    ASCII = 2


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


class WriteMaskReqPdu(typing.NamedTuple):
    address: int
    and_mask: int
    or_mask: int


class WriteMaskResPdu(typing.NamedTuple):
    address: int
    and_mask: int
    or_mask: int


class WriteMaskErrPdu(typing.NamedTuple):
    error: Error


ReqPdu = type('ReqPdu', (abc.ABC, ), {})
ReqPdu.register(ReadReqPdu)
ReqPdu.register(WriteSingleReqPdu)
ReqPdu.register(WriteMultipleReqPdu)
ReqPdu.register(WriteMaskReqPdu)

ResPdu = type('ResPdu', (abc.ABC, ), {})
ResPdu.register(ReadResPdu)
ResPdu.register(WriteSingleResPdu)
ResPdu.register(WriteMultipleResPdu)
ResPdu.register(WriteMaskResPdu)

ErrPdu = type('ErrPdu', (abc.ABC, ), {})
ErrPdu.register(ReadErrPdu)
ErrPdu.register(WriteSingleErrPdu)
ErrPdu.register(WriteMultipleErrPdu)
ErrPdu.register(WriteMaskErrPdu)

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
