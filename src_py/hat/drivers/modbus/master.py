"""Modbus master"""

import asyncio
import logging
import typing

from hat import aio
from hat import util
from hat.drivers import serial
from hat.drivers import tcp
from hat.drivers.modbus import common
from hat.drivers.modbus import encoder
from hat.drivers.modbus import messages
from hat.drivers.modbus import transport


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


async def create_tcp_master(modbus_type: common.ModbusType,
                            addr: tcp.Address,
                            **kwargs
                            ) -> 'Master':
    """Create TCP master

    Args:
        modbus_type: modbus type
        addr: remote host address
        kwargs: additional arguments used for creating TCP connection
            (see `tcp.connect`)

    """
    conn = await tcp.connect(addr, **kwargs)
    reader = transport.TcpReader(conn)
    writer = transport.TcpWriter(conn)
    return _create_master(modbus_type, conn.async_group, reader, writer)


async def create_serial_master(modbus_type: common.ModbusType,
                               port: str, *,
                               silent_interval: float = 0.005,
                               **kwargs
                               ) -> 'Master':
    """Create serial master

    Args:
        modbus_type: modbus type
        port: port name (see `serial.create`)
        silent_interval: silent interval (see `serial.create`)
        kwargs: additional arguments used for opening serial connection
            (see `serial.create`)

    """
    conn = await serial.create(port, silent_interval=silent_interval, **kwargs)
    reader = transport.SerialReader(conn)
    writer = transport.SerialWriter(conn)
    return _create_master(modbus_type, conn.async_group, reader, writer)


def _create_master(modbus_type, async_group, reader, writer):
    master = Master()
    master._modbus_type = modbus_type
    master._async_group = async_group
    master._reader = reader
    master._writer = writer
    master._send_queue = aio.Queue()
    master._receive_cbs = util.CallbackRegistry()
    master._async_group.spawn(master._send_loop)
    master._async_group.spawn(master._receive_loop)
    return master


class Master(aio.Resource):
    """Modbus master

    For creating new instances of this class see
    :func:`create_tcp_master` or :func:`create_serial_master`.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def read(self,
                   device_id: int,
                   data_type: common.DataType,
                   start_address: int,
                   quantity: int = 1
                   ) -> typing.Union[typing.List[int], common.Error]:
        """Read data from modbus device

        Argument `quantity` is ignored if `data_type` is `QUEUE`.

        Args:
            device_id: slave device identifier
            data_type: data type
            start_address: starting modbus data address
            quantity: number of data values

        Raises:
            ConnectionError

        """
        if device_id == 0:
            raise ValueError('unsupported device id')

        if data_type == common.DataType.COIL:
            req = messages.ReadCoilsReq(address=start_address,
                                        quantity=quantity)

        elif data_type == common.DataType.DISCRETE_INPUT:
            req = messages.ReadDiscreteInputsReq(address=start_address,
                                                 quantity=quantity)

        elif data_type == common.DataType.HOLDING_REGISTER:
            req = messages.ReadHoldingRegistersReq(address=start_address,
                                                   quantity=quantity)

        elif data_type == common.DataType.INPUT_REGISTER:
            req = messages.ReadInputRegistersReq(address=start_address,
                                                 quantity=quantity)

        elif data_type == common.DataType.QUEUE:
            req = messages.ReadFifoQueueReq(address=start_address)

        else:
            raise ValueError('unsupported data type')

        res = await self._send(device_id, req)

        if isinstance(res, messages.Response):
            return (res.values if data_type == common.DataType.QUEUE
                    else res.values[:quantity])

        if isinstance(res, common.Error):
            return res

        raise ValueError("unsupported response pdu data")

    async def write(self,
                    device_id: int,
                    data_type: common.DataType,
                    start_address: int,
                    values: typing.List[int]
                    ) -> typing.Optional[common.Error]:
        """Write data to modbus device

        Data types `DISCRETE_INPUT`, `INPUT_REGISTER` and `QUEUE` are not
        supported.

        Args:
            device_id: slave device identifier
            data_type: data type
            start_address: starting modbus data address
            values: values

        Raises:
            ConnectionError

        """
        if data_type == common.DataType.COIL:
            if len(values) == 1:
                req = messages.WriteSingleCoilReq(address=start_address,
                                                  value=values[0])
            else:
                req = messages.WriteMultipleCoilsReq(address=start_address,
                                                     values=values)

        elif data_type == common.DataType.HOLDING_REGISTER:
            if len(values) == 1:
                req = messages.WriteSingleRegisterReq(address=start_address,
                                                      value=values[0])
            else:
                req = messages.WriteMultipleRegistersReq(address=start_address,
                                                         values=values)

        else:
            raise ValueError('unsupported data type')

        res = await self._send(device_id, req)
        if res is None:
            return

        if isinstance(res, messages.Response):
            if (res.address != start_address):
                raise Exception("invalid response pdu address")
            if len(values) == 1:
                if (res.value != values[0]):
                    raise Exception("invalid response pdu value")
            else:
                if (res.quantity != len(values)):
                    raise Exception("invalid response pdu quantity")
            return

        if isinstance(res, common.Error):
            return res

        raise ValueError("unsupported response pdu data")

    async def write_mask(self,
                         device_id: int,
                         address: int,
                         and_mask: int,
                         or_mask: int
                         ) -> typing.Optional[common.Error]:
        """Write mask to modbus device HOLDING_REGISTER

        Args:
            device_id: slave device identifier
            address: modbus data address
            and_mask: and mask
            or_mask: or mask

        Raises:
            ConnectionError

        """
        req = messages.MaskWriteRegisterReq(address=address,
                                            and_mask=and_mask,
                                            or_mask=or_mask)

        res = await self._send(device_id, req)
        if res is None:
            return

        if isinstance(res, messages.Response):
            if (res.address != address):
                raise Exception("invalid response pdu address")
            if (res.and_mask != and_mask):
                raise Exception("invalid response pdu and mask")
            if (res.or_mask != or_mask):
                raise Exception("invalid response pdu or mask")
            return

        if isinstance(res, common.Error):
            return res

        raise ValueError("unsupported response pdu data")

    async def _send(self, device_id, req):
        req_pdu = messages.Pdu(fc=_get_req_fc(req), data=req)
        future = asyncio.Future()

        try:
            self._send_queue.put_nowait((device_id, req_pdu, future))

        except aio.QueueClosedError:
            raise ConnectionError()

        res_pdu = await future
        if res_pdu.fc != req_pdu.fc:
            raise Exception("invalid response function code")

        return res_pdu.data

    async def _send_loop(self):
        transaction_id = 0
        future = None

        try:
            while True:
                device_id, req_pdu, future = await self._send_queue.get()
                if future.done():
                    continue

                if self._modbus_type == common.ModbusType.TCP:
                    transaction_id += 1
                    req_adu = messages.TcpAdu(transaction_id=transaction_id,
                                              device_id=device_id,
                                              pdu=req_pdu)

                elif self._modbus_type == common.ModbusType.RTU:
                    req_adu = messages.RtuAdu(device_id=device_id,
                                              pdu=req_pdu)

                elif self._modbus_type == common.ModbusType.ASCII:
                    req_adu = messages.AsciiAdu(device_id=device_id,
                                                pdu=req_pdu)

                else:
                    raise Exception("invalid modbus type")

                try:
                    req_adu_bytes = encoder.encode_adu(req_adu)
                except Exception as e:
                    future.set_exception(e)
                    continue

                res_adu_queue = aio.Queue()
                with self._receive_cbs.register(res_adu_queue.put_nowait):

                    await self._writer.write(req_adu_bytes)

                    if device_id == 0:
                        res_pdu = messages.Pdu(req_pdu.fc, None)
                    else:
                        res_pdu = None

                    while not res_pdu:
                        async with self.async_group.create_subgroup() as subgroup: # NOQA
                            res_adu_future = subgroup.spawn(res_adu_queue.get)
                            await asyncio.wait(
                                [res_adu_future, future],
                                return_when=asyncio.FIRST_COMPLETED)
                            if future.done():
                                break
                            res_adu = res_adu_future.result()

                        if self._modbus_type == common.ModbusType.TCP:
                            if req_adu.transaction_id != res_adu.transaction_id:  # NOQA
                                mlog.warning("received invalid response "
                                             "transaction id")
                                continue

                        if req_adu.device_id != res_adu.device_id:
                            mlog.warning("received invalid response "
                                         "device id")
                            continue

                        res_pdu = res_adu.pdu

                if not future.done():
                    future.set_result(res_pdu)

        except Exception as e:
            mlog.error("error in send loop: %s", e, exc_info=e)

        finally:
            self.close()
            self._send_queue.close()
            if future and not future.done():
                future.set_exception(ConnectionError())
            while not self._send_queue.empty():
                _, __, future = self._send_queue.get_nowait()
                if not future.done():
                    future.set_exception(ConnectionError())

    async def _receive_loop(self):
        try:
            while True:
                adu = await encoder.read_adu(self._modbus_type,
                                             encoder.Direction.RESPONSE,
                                             self._reader)
                self._receive_cbs.notify(adu)

        except Exception as e:
            mlog.error("error in read loop: %s", e, exc_info=e)

        finally:
            self.close()


def _get_req_fc(req):
    if isinstance(req, messages.ReadCoilsReq):
        return messages.FunctionCode.READ_COILS

    if isinstance(req, messages.ReadDiscreteInputsReq):
        return messages.FunctionCode.READ_DISCRETE_INPUTS

    if isinstance(req, messages.ReadHoldingRegistersReq):
        return messages.FunctionCode.READ_HOLDING_REGISTERS

    if isinstance(req, messages.ReadInputRegistersReq):
        return messages.FunctionCode.READ_INPUT_REGISTERS

    if isinstance(req, messages.WriteSingleCoilReq):
        return messages.FunctionCode.WRITE_SINGLE_COIL

    if isinstance(req, messages.WriteSingleRegisterReq):
        return messages.FunctionCode.WRITE_SINGLE_REGISTER

    if isinstance(req, messages.WriteMultipleCoilsReq):
        return messages.FunctionCode.WRITE_MULTIPLE_COILS

    if isinstance(req, messages.WriteMultipleRegistersReq):
        return messages.FunctionCode.WRITE_MULTIPLE_REGISTER

    if isinstance(req, messages.MaskWriteRegisterReq):
        return messages.FunctionCode.MASK_WRITE_REGISTER

    if isinstance(req, messages.ReadFifoQueueReq):
        return messages.FunctionCode.READ_FIFO_QUEUE

    raise ValueError('unsupported request type')
