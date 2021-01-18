"""Modbus slave"""

import asyncio
import contextlib
import logging
import typing

from hat import aio
from hat.drivers import serial
from hat.drivers.modbus import common
from hat.drivers.modbus import encoder


mlog = logging.getLogger(__name__)


SlaveCb = aio.AsyncCallable[['Slave'], None]

ReadCb = aio.AsyncCallable[['Slave',  # slave
                            int,  # device_id
                            common.DataType,  # data_type
                            int,  # start_address
                            typing.Optional[int]  # quantity
                            ], typing.Union[typing.List[int], common.Error]]

WriteCb = aio.AsyncCallable[['Slave',  # slave
                             int,  # device_id
                             common.DataType,  # data_type
                             int,  # start_address
                             typing.List[int]  # values
                             ], typing.Optional[common.Error]]


async def create_tcp_server(modbus_type: common.ModbusType,
                            host: str,
                            port: int,
                            slave_cb: SlaveCb,
                            read_cb: ReadCb,
                            write_cb: WriteCb
                            ) -> 'TcpServer':
    """Create TCP server

    Args:
        modbus_type: modbus type
        host: local listening host name
        port: local listening TCP port
        slave_cb: slave callback
        read_cb: read callback
        write_cb: write callback

    """
    server = TcpServer()
    server._modbus_type = modbus_type
    server._slave_cb = slave_cb
    server._read_cb = read_cb
    server._write_cb = write_cb
    server._async_group = aio.Group(exception_cb=_on_exception)
    server._srv = await asyncio.start_server(
        lambda r, w: server._async_group.spawn(server._on_connection, r, w),
        host, port)
    server._async_group.spawn(aio.call_on_cancel, server._on_close)
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
    reader = common.SerialReader(conn)
    writer = common.SerialWriter(conn)
    return _create_slave(aio.Group(exception_cb=_on_exception), modbus_type,
                         read_cb, write_cb, reader, writer)


class TcpServer(aio.Resource):
    """TCP server

    For creating new instances of this class see :func:`create_tcp_server`.

    Closing server closes all active associated slaves.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def _on_close(self):
        with contextlib.suppress(Exception):
            self._srv.close()
        with contextlib.suppress(ConnectionError):
            await self._srv.wait_closed()

    async def _on_connection(self, reader, writer):
        async_group = self._async_group.create_subgroup()
        reader = common.TcpReader(reader)
        writer = common.TcpWriter(writer)
        slave = _create_slave(async_group, self._modbus_type,
                              self._read_cb, self._write_cb, reader, writer)
        try:
            await aio.call(self._slave_cb, slave)
        except Exception as e:
            mlog.error('error in slave callback: %s', e, exc_info=e)
            await slave.async_close()


def _create_slave(async_group, modbus_type, read_cb, write_cb, reader, writer):
    slave = Slave()
    slave._async_group = async_group
    slave._modbus_type = modbus_type
    slave._read_cb = read_cb
    slave._write_cb = write_cb
    slave._reader = reader
    slave._writer = writer
    slave._async_group.spawn(aio.call_on_cancel, writer.async_close)
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
                except (asyncio.IncompleteReadError, EOFError):
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
            self._async_group.close()


def _on_exception(exc):
    mlog.error("modbus slave error: %s", exc, exc_info=exc)
