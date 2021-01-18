"""Modbus master"""

import asyncio
import logging
import typing

from hat import aio
from hat.drivers import serial
from hat.drivers.modbus import common
from hat.drivers.modbus import encoder


mlog = logging.getLogger(__name__)


async def create_tcp_master(modbus_type: common.ModbusType,
                            host: str,
                            port: int
                            ) -> 'Master':
    """Create TCP master

    Args:
        modbus_type: modbus type
        host: remote host name
        port: remote TCP port

    """
    reader, writer = await asyncio.open_connection(host, port)
    reader = common.TcpReader(reader)
    writer = common.TcpWriter(writer)
    return _create_master(modbus_type, reader, writer)


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
    reader = common.SerialReader(conn)
    writer = common.SerialWriter(conn)
    return _create_master(modbus_type, reader, writer)


def _create_master(modbus_type, reader, writer):
    master = Master()
    master._modbus_type = modbus_type
    master._reader = reader
    master._writer = writer
    master._send_queue = aio.Queue()
    master._async_group = aio.Group(exception_cb=_on_exception)
    master._async_group.spawn(aio.call_on_cancel, writer.async_close)
    master._async_group.spawn(master._send_loop)
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
        quantity = quantity if data_type != common.DataType.QUEUE else None
        req_pdu = common.ReadReqPdu(data_type=data_type,
                                    address=start_address,
                                    quantity=quantity)

        future = asyncio.Future()
        try:
            self._send_queue.put_nowait((device_id, req_pdu, future))
        except aio.QueueClosedError:
            raise ConnectionError()
        res_pdu = await future

        if isinstance(res_pdu, common.ReadResPdu):
            if data_type == common.DataType.QUEUE:
                return res_pdu.values
            return res_pdu.values[:quantity]

        if isinstance(res_pdu, common.ReadErrPdu):
            return res_pdu.error

        raise Exception("invalid response pdu type")

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
        req_pdu = common.WriteMultipleReqPdu(data_type=data_type,
                                             address=start_address,
                                             values=values)

        future = asyncio.Future()
        try:
            self._send_queue.put_nowait((device_id, req_pdu, future))
        except aio.QueueClosedError:
            raise ConnectionError()
        res_pdu = await future

        if isinstance(res_pdu, common.WriteMultipleResPdu):
            if (res_pdu.address != start_address):
                raise Exception("invalid response pdu address")
            if (res_pdu.quantity != len(values)):
                raise Exception("invalid response pdu quantity")
            return

        if isinstance(res_pdu, common.WriteMultipleErrPdu):
            return res_pdu.error

        raise Exception("invalid response pdu type")

    async def _send_loop(self):
        transaction_id = 0
        future = None

        try:
            while True:
                device_id, req_pdu, future = await self._send_queue.get()

                if self._modbus_type == common.ModbusType.TCP:
                    transaction_id += 1
                    req_adu = common.TcpAdu(transaction_id=transaction_id,
                                            device_id=device_id,
                                            pdu=req_pdu)

                elif self._modbus_type == common.ModbusType.RTU:
                    req_adu = common.RtuAdu(device_id=device_id,
                                            pdu=req_pdu)

                elif self._modbus_type == common.ModbusType.ASCII:
                    req_adu = common.AsciiAdu(device_id=device_id,
                                              pdu=req_pdu)

                else:
                    raise Exception("invalid modbus type")

                try:
                    req_adu_bytes = encoder.encode_adu(req_adu)
                except Exception as e:
                    future.set_exception(e)
                    continue
                await self._writer.write(req_adu_bytes)

                res_adu = await encoder.read_adu(self._modbus_type,
                                                 common.Direction.RESPONSE,
                                                 self._reader)

                if self._modbus_type == common.ModbusType.TCP:
                    if req_adu.transaction_id != res_adu.transaction_id:
                        raise Exception("invalid response transaction id")

                if req_adu.device_id:
                    if req_adu.device_id != res_adu.device_id:
                        raise Exception("invalid response device id")

                if isinstance(req_adu.pdu, common.ReadReqPdu):
                    if (not isinstance(res_adu.pdu, common.ReadResPdu)
                            and not isinstance(res_adu.pdu,
                                               common.ReadErrPdu)):
                        raise Exception("invalid response pdu type")

                elif isinstance(req_adu.pdu, common.WriteSingleReqPdu):
                    if (not isinstance(res_adu.pdu, common.WriteSingleResPdu)
                            and not isinstance(res_adu.pdu,
                                               common.WriteSingleErrPdu)):
                        raise Exception("invalid response pdu type")

                elif isinstance(req_adu.pdu, common.WriteMultipleReqPdu):
                    if (not isinstance(res_adu.pdu, common.WriteMultipleResPdu)
                            and not isinstance(res_adu.pdu,
                                               common.WriteMultipleErrPdu)):
                        raise Exception("invalid response pdu type")

                else:
                    raise Exception("unsupported request pdu type")

                if req_adu.pdu.data_type != res_adu.pdu.data_type:
                    raise Exception("invalid response data type")

                if not future.done():
                    future.set_result(res_adu.pdu)

        finally:
            if future and not future.done():
                future.set_exception(ConnectionError())
            while not self._send_queue.empty():
                future = self._send_queue.get_nowait()
                future.set_exception(ConnectionError())
            self._send_queue.close()
            self._async_group.close()


def _on_exception(exc):
    mlog.error("modbus master error: %s", exc, exc_info=exc)
