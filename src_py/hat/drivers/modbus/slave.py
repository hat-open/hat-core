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


async def create_tcp_server(modbus_type: common.ModbusType,
                            addr: tcp.Address,
                            slave_cb: SlaveCb,
                            read_cb: ReadCb,
                            write_cb: WriteCb,
                            **kwargs
                            ) -> 'TcpServer':
    """Create TCP server

    Args:
        modbus_type: modbus type
        addr: local listening host address
        slave_cb: slave callback
        read_cb: read callback
        write_cb: write callback
        kwargs: additional arguments used for creating TCP server
            (see `tcp.listen`)

    """
    server = TcpServer()
    server._modbus_type = modbus_type
    server._slave_cb = slave_cb
    server._read_cb = read_cb
    server._write_cb = write_cb
    server._srv = await tcp.listen(server._on_connection, addr,
                                   bind_connections=True, **kwargs)
    return server


async def create_serial_slave(modbus_type: common.ModbusType,
                              port: str,
                              read_cb: ReadCb,
                              write_cb: WriteCb, *,
                              silent_interval: float = 0.005,
                              **kwargs
                              ) -> 'Slave':
    """Create serial slave

    Args:
        modbus_type: modbus type
        port: port name (see `serial.create`)
        read_cb: read callback
        write_cb: write callback
        silent_interval: silent interval (see `serial.create`)
        kwargs: additional arguments used for opening serial connection
            (see `serial.create`)

    """
    conn = await serial.create(port, silent_interval=silent_interval, **kwargs)
    reader = transport.SerialReader(conn)
    writer = transport.SerialWriter(conn)
    return _create_slave(conn.async_group, modbus_type, read_cb, write_cb,
                         reader, writer)


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
                              self._read_cb, self._write_cb, reader, writer)
        try:
            await aio.call(self._slave_cb, slave)
        except Exception as e:
            mlog.error('error in slave callback: %s', e, exc_info=e)
            slave.close()


def _create_slave(async_group, modbus_type, read_cb, write_cb, reader, writer):
    slave = Slave()
    slave._async_group = async_group
    slave._modbus_type = modbus_type
    slave._read_cb = read_cb
    slave._write_cb = write_cb
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
                                                     common.Direction.REQUEST,
                                                     self._reader)
                except (asyncio.IncompleteReadError,
                        EOFError,
                        ConnectionError):
                    break

                if isinstance(req_adu.pdu, common.ReadReqPdu):
                    result = await aio.call(self._read_cb, self,
                                            req_adu.device_id,
                                            req_adu.pdu.data_type,
                                            req_adu.pdu.address,
                                            req_adu.pdu.quantity)
                    if isinstance(result, common.Error):
                        res_pdu = common.ReadErrPdu(
                            data_type=req_adu.pdu.data_type,
                            error=result)
                    else:
                        res_pdu = common.ReadResPdu(
                            data_type=req_adu.pdu.data_type,
                            values=result)

                elif isinstance(req_adu.pdu, common.WriteSingleReqPdu):
                    result = await aio.call(self._write_cb, self,
                                            req_adu.device_id,
                                            req_adu.pdu.data_type,
                                            req_adu.pdu.address,
                                            [req_adu.pdu.value])
                    if isinstance(result, common.Error):
                        res_pdu = common.WriteSingleErrPdu(
                            data_type=req_adu.pdu.data_type,
                            error=result)
                    else:
                        res_pdu = common.WriteSingleResPdu(
                            data_type=req_adu.pdu.data_type,
                            address=req_adu.pdu.address,
                            value=req_adu.pdu.value)

                elif isinstance(req_adu.pdu, common.WriteMultipleReqPdu):
                    result = await aio.call(self._write_cb, self,
                                            req_adu.device_id,
                                            req_adu.pdu.data_type,
                                            req_adu.pdu.address,
                                            req_adu.pdu.values)
                    if isinstance(result, common.Error):
                        res_pdu = common.WriteMultipleErrPdu(
                            data_type=req_adu.pdu.data_type,
                            error=result)
                    else:
                        res_pdu = common.WriteMultipleResPdu(
                            data_type=req_adu.pdu.data_type,
                            address=req_adu.pdu.address,
                            quantity=len(req_adu.pdu.values))

                else:
                    raise Exception("invalid request pdu type")

                if self._modbus_type == common.ModbusType.TCP:
                    res_adu = common.TcpAdu(
                        transaction_id=req_adu.transaction_id,
                        device_id=req_adu.device_id,
                        pdu=res_pdu)

                elif self._modbus_type == common.ModbusType.RTU:
                    res_adu = common.RtuAdu(device_id=req_adu.device_id,
                                            pdu=res_pdu)

                elif self._modbus_type == common.ModbusType.ASCII:
                    res_adu = common.AsciiAdu(device_id=req_adu.device_id,
                                              pdu=res_pdu)

                else:
                    raise Exception("invalid modbus type")

                res_adu_bytes = encoder.encode_adu(res_adu)
                await self._writer.write(res_adu_bytes)

        finally:
            self.close()
