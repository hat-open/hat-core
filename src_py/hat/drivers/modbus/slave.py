"""Modbus slave"""

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


SlaveCb = aio.AsyncCallable[['Slave'], None]
"""Slave callback

Args:
    slave: slave instance

"""
util.register_type_alias('SlaveCb')


ReadCb = aio.AsyncCallable[['Slave',
                            int,
                            common.DataType,
                            int,
                            typing.Optional[int]
                            ], typing.Union[typing.List[int], common.Error]]
"""Read callback

Args:
    slave: slave instance
    device_id: device identifier
    data_type: data type
    start_address: staring address
    quantity: number of registers

Returns:
    list of register values or error

"""
util.register_type_alias('ReadCb')


WriteCb = aio.AsyncCallable[['Slave',
                             int,
                             common.DataType,
                             int,
                             typing.List[int]
                             ], typing.Optional[common.Error]]
"""Write callback

Args:
    slave: slave instance
    device_id: device identifier
    data_type: data type
    start_address: staring address
    values: register values

Returns:
    ``None`` on success or error

"""
util.register_type_alias('WriteCb')


WriteMaskCb = aio.AsyncCallable[['Slave',
                                 int,
                                 int,
                                 int,
                                 int
                                 ], typing.Optional[common.Error]]
"""Write mask callback

Args:
    slave: slave instance
    device_id: device identifier
    address: address
    and_mask: and mask
    or_mask: or mask

Returns:
    ``None`` on success or error

"""
util.register_type_alias('WriteMaskCb')


async def create_tcp_server(modbus_type: common.ModbusType,
                            addr: tcp.Address,
                            slave_cb: typing.Optional[SlaveCb] = None,
                            read_cb: typing.Optional[ReadCb] = None,
                            write_cb: typing.Optional[WriteCb] = None,
                            write_mask_cb: typing.Optional[WriteMaskCb] = None,
                            **kwargs
                            ) -> 'TcpServer':
    """Create TCP server

    Args:
        modbus_type: modbus type
        addr: local listening host address
        slave_cb: slave callback
        read_cb: read callback
        write_cb: write callback
        write_mask_cb: write mask callback
        kwargs: additional arguments used for creating TCP server
            (see `tcp.listen`)

    """
    server = TcpServer()
    server._modbus_type = modbus_type
    server._slave_cb = slave_cb
    server._read_cb = read_cb
    server._write_cb = write_cb
    server._write_mask_cb = write_mask_cb
    server._srv = await tcp.listen(server._on_connection, addr,
                                   bind_connections=True, **kwargs)
    return server


async def create_serial_slave(modbus_type: common.ModbusType,
                              port: str,
                              read_cb: typing.Optional[ReadCb] = None,
                              write_cb: typing.Optional[WriteCb] = None,
                              write_mask_cb: typing.Optional[WriteMaskCb] = None,  # NOQA
                              silent_interval: float = 0.005,
                              **kwargs
                              ) -> 'Slave':
    """Create serial slave

    Args:
        modbus_type: modbus type
        port: port name (see `serial.create`)
        read_cb: read callback
        write_cb: write callback
        write_mask_cb: write mask callback
        silent_interval: silent interval (see `serial.create`)
        kwargs: additional arguments used for opening serial connection
            (see `serial.create`)

    """
    conn = await serial.create(port, silent_interval=silent_interval, **kwargs)
    reader = transport.SerialReader(conn)
    writer = transport.SerialWriter(conn)
    return _create_slave(conn.async_group, modbus_type, read_cb, write_cb,
                         write_mask_cb, reader, writer)


class TcpServer(aio.Resource):
    """TCP server

    For creating new instances of this class see :func:`create_tcp_server`.

    Closing server closes all active associated slaves.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._srv.async_group

    async def _on_connection(self, conn):
        reader = transport.TcpReader(conn)
        writer = transport.TcpWriter(conn)
        slave = _create_slave(conn.async_group, self._modbus_type,
                              self._read_cb, self._write_cb,
                              self._write_mask_cb, reader, writer)

        if not self._slave_cb:
            return

        try:
            await aio.call(self._slave_cb, slave)
        except Exception as e:
            mlog.error('error in slave callback: %s', e, exc_info=e)
            slave.close()


def _create_slave(async_group, modbus_type, read_cb, write_cb, write_mask_cb,
                  reader, writer):
    slave = Slave()
    slave._async_group = async_group
    slave._modbus_type = modbus_type
    slave._read_cb = read_cb
    slave._write_cb = write_cb
    slave._write_mask_cb = write_mask_cb
    slave._reader = reader
    slave._writer = writer
    slave._async_group.spawn(slave._receive_loop)
    return slave


class Slave(aio.Resource):
    """Modbus slave

    For creating new instances of this class see
    :func:`create_tcp_server` or :func:`create_serial_slave`.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def _receive_loop(self):
        try:
            while True:
                try:
                    req_adu = await encoder.read_adu(self._modbus_type,
                                                     encoder.Direction.REQUEST,
                                                     self._reader)
                except (asyncio.IncompleteReadError,
                        EOFError,
                        ConnectionError):
                    break

                device_id = req_adu.device_id
                fc = req_adu.pdu.fc
                req = req_adu.pdu.data

                res = await self._process_request(device_id, fc, req)
                res_pdu = messages.Pdu(fc=fc, data=res)

                if device_id == 0:
                    continue

                if self._modbus_type == common.ModbusType.TCP:
                    res_adu = messages.TcpAdu(
                        transaction_id=req_adu.transaction_id,
                        device_id=req_adu.device_id,
                        pdu=res_pdu)

                elif self._modbus_type == common.ModbusType.RTU:
                    res_adu = messages.RtuAdu(device_id=req_adu.device_id,
                                              pdu=res_pdu)

                elif self._modbus_type == common.ModbusType.ASCII:
                    res_adu = messages.AsciiAdu(device_id=req_adu.device_id,
                                                pdu=res_pdu)

                else:
                    raise ValueError("invalid modbus type")

                res_adu_bytes = encoder.encode_adu(res_adu)
                await self._writer.write(res_adu_bytes)

        finally:
            self.close()

    async def _process_request(self, device_id, fc, req):
        if fc == messages.FunctionCode.READ_COILS:
            if self._read_cb:
                data_type = common.DataType.COIL
                result = await aio.call(self._read_cb, self, device_id,
                                        data_type, req.address, req.quantity)
            else:
                result = common.Error.FUNCTION_ERROR

            if isinstance(result, common.Error):
                return result

            return messages.ReadCoilsRes(values=result)

        if fc == messages.FunctionCode.READ_DISCRETE_INPUTS:
            if self._read_cb:
                data_type = common.DataType.DISCRETE_INPUT
                result = await aio.call(self._read_cb, self, device_id,
                                        data_type, req.address, req.quantity)
            else:
                result = common.Error.FUNCTION_ERROR

            if isinstance(result, common.Error):
                return result

            return messages.ReadDiscreteInputsRes(values=result)

        if fc == messages.FunctionCode.READ_HOLDING_REGISTERS:
            if self._read_cb:
                data_type = common.DataType.HOLDING_REGISTER
                result = await aio.call(self._read_cb, self, device_id,
                                        data_type, req.address, req.quantity)
            else:
                result = common.Error.FUNCTION_ERROR

            if isinstance(result, common.Error):
                return result

            return messages.ReadHoldingRegistersRes(values=result)

        if fc == messages.FunctionCode.READ_INPUT_REGISTERS:
            if self._read_cb:
                data_type = common.DataType.INPUT_REGISTER
                result = await aio.call(self._read_cb, self, device_id,
                                        data_type, req.address, req.quantity)
            else:
                result = common.Error.FUNCTION_ERROR

            if isinstance(result, common.Error):
                return result

            return messages.ReadInputRegistersRes(values=result)

        if fc == messages.FunctionCode.WRITE_SINGLE_COIL:
            if self._write_cb:
                data_type = common.DataType.COIL
                result = await aio.call(self._write_cb, self, device_id,
                                        data_type, req.address, [req.value])
            else:
                result = common.Error.FUNCTION_ERROR

            if isinstance(result, common.Error):
                return result

            return messages.WriteSingleCoilRes(address=req.address,
                                               value=req.value)

        if fc == messages.FunctionCode.WRITE_SINGLE_REGISTER:
            if self._write_cb:
                data_type = common.DataType.HOLDING_REGISTER
                result = await aio.call(self._write_cb, self, device_id,
                                        data_type, req.address, [req.value])
            else:
                result = common.Error.FUNCTION_ERROR

            if isinstance(result, common.Error):
                return result

            return messages.WriteSingleRegisterRes(address=req.address,
                                                   value=req.value)

        if fc == messages.FunctionCode.WRITE_MULTIPLE_COILS:
            if self._write_cb:
                data_type = common.DataType.COIL
                result = await aio.call(self._write_cb, self, device_id,
                                        data_type, req.address, req.values)
            else:
                result = common.Error.FUNCTION_ERROR

            if isinstance(result, common.Error):
                return result

            return messages.WriteMultipleCoilsRes(address=req.address,
                                                  quantity=len(req.values))

        if fc == messages.FunctionCode.WRITE_MULTIPLE_REGISTER:
            if self._write_cb:
                data_type = common.DataType.HOLDING_REGISTER
                result = await aio.call(self._write_cb, self, device_id,
                                        data_type, req.address, req.values)
            else:
                result = common.Error.FUNCTION_ERROR

            if isinstance(result, common.Error):
                return result

            return messages.WriteMultipleRegistersRes(address=req.address,
                                                      quantity=len(req.values))

        if fc == messages.FunctionCode.MASK_WRITE_REGISTER:
            if self._write_mask_cb:
                result = await aio.call(self._write_mask_cb, self, device_id,
                                        req.address, req.and_mask, req.or_mask)
            else:
                result = common.Error.FUNCTION_ERROR

            if isinstance(result, common.Error):
                return result

            return messages.MaskWriteRegisterRes(address=req.address,
                                                 and_mask=req.and_mask,
                                                 or_mask=req.or_mask)

        if fc == messages.FunctionCode.READ_FIFO_QUEUE:
            if self._read_cb:
                data_type = common.DataType.QUEUE
                result = await aio.call(self._read_cb, self, device_id,
                                        data_type, req.address, None)
            else:
                result = common.Error.FUNCTION_ERROR

            if isinstance(result, common.Error):
                return result

            return messages.ReadFifoQueueRes(values=result)

        return common.Error.INVALID_FUNCTION_CODE
