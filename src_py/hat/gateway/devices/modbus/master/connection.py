import asyncio
import contextlib
import enum
import logging
import typing

from hat import json
from hat import aio
from hat.drivers import modbus
from hat.drivers import serial
from hat.drivers import tcp


mlog = logging.getLogger(__name__)


DataType = modbus.DataType


Error = enum.Enum('Error', [
    'INVALID_FUNCTION_CODE',
    'INVALID_DATA_ADDRESS',
    'INVALID_DATA_VALUE',
    'FUNCTION_ERROR',
    'TIMEOUT'])


async def connect(conf: json.Data) -> 'Connection':
    transport_conf = conf['transport']
    modbus_type = modbus.ModbusType[conf['modbus_type']]

    if transport_conf['type'] == 'TCP':
        addr = tcp.Address(transport_conf['host'], transport_conf['port'])
        master = await modbus.create_tcp_master(modbus_type=modbus_type,
                                                addr=addr)

    elif transport_conf['type'] == 'SERIAL':
        port = transport_conf['port']
        baudrate = transport_conf['baudrate']
        bytesize = serial.ByteSize[transport_conf['bytesize']]
        parity = serial.Parity[transport_conf['parity']]
        stopbits = serial.StopBits[transport_conf['stopbits']]
        xonxoff = transport_conf['flow_control']['xonxoff']
        rtscts = transport_conf['flow_control']['rtscts']
        dsrdtr = transport_conf['flow_control']['dsrdtr']
        silent_interval = transport_conf['silent_interval']
        master = await modbus.create_serial_master(
            modbus_type=modbus_type,
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            xonxoff=xonxoff,
            rtscts=rtscts,
            dsrdtr=dsrdtr,
            silent_interval=silent_interval)

    else:
        raise ValueError('unsupported link type')

    conn = Connection()
    conn._conf = conf
    conn._master = master
    conn._request_queue = aio.Queue()

    conn.async_group.spawn(conn._request_loop)

    return conn


class Connection(aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        return self._master.async_group

    async def read(self,
                   device_id: int,
                   data_type: modbus.DataType,
                   start_address: int,
                   quantity: int
                   ) -> typing.Union[typing.List[int], Error]:
        return self._request(self._master.read, device_id, data_type,
                             start_address, quantity)

    async def write(self,
                    device_id: int,
                    data_type: modbus.DataType,
                    start_address: int,
                    values: typing.List[int]
                    ) -> typing.Optional[Error]:
        return self._request(self._master.write, device_id, data_type,
                             start_address, values)

    async def write_mask(self,
                         device_id: int,
                         address: int,
                         and_mask: int,
                         or_mask: int
                         ) -> typing.Optional[Error]:
        return await self._request(self._master.write_mask, device_id,
                                   address, and_mask, or_mask)

    async def _request_loop(self):
        future = None

        try:
            while True:
                fn, args, future = await self._request_queue.get()
                if future.done():
                    continue

                try:
                    result = await self._communicate(fn, *args)
                    if not future.done():
                        future.set_result(result)
                except Exception as e:
                    future.set_exception(e)

        except Exception as e:
            mlog.error('request loop error: %s', e, exc_info=e)

        finally:
            self.close()
            self._request_queue.close()
            if future and not future.done():
                future.set_exception(ConnectionError())
            while not self._request_queue.empty():
                _, __, future = self._request_queue.get_nowait()
                if not future.done():
                    future.set_exception(ConnectionError())

    async def _request(self, fn, *args):
        try:
            future = asyncio.Future()
            self._request_queue.put_nowait((fn, args, future))
            return await future

        except aio.QueueClosedError:
            raise ConnectionError()

    async def _communicate(self, fn, *args):
        for retry_count in range(self._conf['request_retry_count']):
            with contextlib.suppres(asyncio.TimeoutError):
                result = await aio.wait_for(fn(*args),
                                            self._conf['request_timeout'])

                if isinstance(result, modbus.Error):
                    return Error[result]

                return result

            if retry_count + 1 != self._conf['request_retry_count']:
                await self._conf['request_retry_delay']

        return Error.TIMEOUT
