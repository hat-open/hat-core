"""Modbus messages"""

import abc
import enum
import typing

from hat.drivers.modbus import common


class FunctionCode(enum.Enum):
    READ_COILS = 1
    READ_DISCRETE_INPUTS = 2
    READ_HOLDING_REGISTERS = 3
    READ_INPUT_REGISTERS = 4
    WRITE_SINGLE_COIL = 5
    WRITE_SINGLE_REGISTER = 6
    WRITE_MULTIPLE_COILS = 15
    WRITE_MULTIPLE_REGISTER = 16
    MASK_WRITE_REGISTER = 22
    READ_FIFO_QUEUE = 24


class ReadCoilsReq(typing.NamedTuple):
    address: int
    quantity: typing.Optional[int]


class ReadCoilsRes(typing.NamedTuple):
    values: typing.List[int]


class ReadDiscreteInputsReq(typing.NamedTuple):
    address: int
    quantity: typing.Optional[int]


class ReadDiscreteInputsRes(typing.NamedTuple):
    values: typing.List[int]


class ReadHoldingRegistersReq(typing.NamedTuple):
    address: int
    quantity: typing.Optional[int]


class ReadHoldingRegistersRes(typing.NamedTuple):
    values: typing.List[int]


class ReadInputRegistersReq(typing.NamedTuple):
    address: int
    quantity: typing.Optional[int]


class ReadInputRegistersRes(typing.NamedTuple):
    values: typing.List[int]


class WriteSingleCoilReq(typing.NamedTuple):
    address: int
    value: int


class WriteSingleCoilRes(typing.NamedTuple):
    address: int
    value: int


class WriteSingleRegisterReq(typing.NamedTuple):
    address: int
    value: int


class WriteSingleRegisterRes(typing.NamedTuple):
    address: int
    value: int


class WriteMultipleCoilsReq(typing.NamedTuple):
    address: int
    values: typing.List[int]


class WriteMultipleCoilsRes(typing.NamedTuple):
    address: int
    quantity: int


class WriteMultipleRegistersReq(typing.NamedTuple):
    address: int
    values: typing.List[int]


class WriteMultipleRegistersRes(typing.NamedTuple):
    address: int
    quantity: int


class MaskWriteRegisterReq(typing.NamedTuple):
    address: int
    and_mask: int
    or_mask: int


class MaskWriteRegisterRes(typing.NamedTuple):
    address: int
    and_mask: int
    or_mask: int


class ReadFifoQueueReq(typing.NamedTuple):
    address: int


class ReadFifoQueueRes(typing.NamedTuple):
    values: typing.List[int]


Request = type('Request', (abc.ABC, ), {})
Request.register(ReadCoilsReq)
Request.register(ReadDiscreteInputsReq)
Request.register(ReadHoldingRegistersReq)
Request.register(ReadInputRegistersReq)
Request.register(WriteSingleCoilReq)
Request.register(WriteSingleRegisterReq)
Request.register(WriteMultipleCoilsReq)
Request.register(WriteMultipleRegistersReq)
Request.register(MaskWriteRegisterReq)
Request.register(ReadFifoQueueReq)


Response = type('Response', (abc.ABC, ), {})
Response.register(ReadCoilsRes)
Response.register(ReadDiscreteInputsRes)
Response.register(ReadHoldingRegistersRes)
Response.register(ReadInputRegistersRes)
Response.register(WriteSingleCoilRes)
Response.register(WriteSingleRegisterRes)
Response.register(WriteMultipleCoilsRes)
Response.register(WriteMultipleRegistersRes)
Response.register(MaskWriteRegisterRes)
Response.register(ReadFifoQueueRes)


class Pdu(typing.NamedTuple):
    fc: FunctionCode
    data: typing.Union[Request, Response, common.Error]


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
