import asyncio
import contextlib
import enum
import typing

from hat import json
from hat import aio
from hat.drivers import modbus
from hat.drivers import serial
from hat.drivers import tcp


Error = enum.Enum('Error', [
    'INVALID_FUNCTION_CODE',
    'INVALID_DATA_ADDRESS',
    'INVALID_DATA_VALUE',
    'FUNCTION_ERROR',
    'TIMEOUT'])


async def connect(conf: json.Data) -> 'Connection':
    link_conf = conf['link']
    modbus_type = modbus.ModbusType[conf['modbus_type']]

    if link_conf['type'] == 'TCP':
        addr = tcp.Address(link_conf['host'], link_conf['port'])
        master = await modbus.create_tcp_master(modbus_type=modbus_type,
                                                addr=addr)

    elif link_conf['type'] == 'SERIAL':
        port = link_conf['port']
        baudrate = link_conf['baudrate']
        bytesize = serial.ByteSize[link_conf['bytesize']]
        parity = serial.Parity[link_conf['parity']]
        stopbits = serial.StopBits[link_conf['stopbits']]
        xonxoff = link_conf['flow_control']['xonxoff']
        rtscts = link_conf['flow_control']['rtscts']
        dsrdtr = link_conf['flow_control']['dsrdtr']
        silent_interval = link_conf['silent_interval']
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
    return conn


class Connection(aio.Resource):

    @property
    def async_group(self):
        return self._master.async_group

    async def read(self,
                   device_id: int,
                   data_type: modbus.DataType,
                   start_address: int,
                   quantity: int
                   ) -> typing.Union[typing.List[int], Error]:
        return await self._request(self._master.read, device_id, data_type,
                                   start_address, quantity)

    async def write(self,
                    device_id: int,
                    data_type: modbus.DataType,
                    start_address: int,
                    values: typing.List[int]
                    ) -> typing.Optional[Error]:
        return await self._request(self._master.write, device_id, data_type,
                                   start_address, values)

    async def write_mask(self,
                         device_id: int,
                         address: int,
                         and_mask: int,
                         or_mask: int
                         ) -> typing.Optional[Error]:
        return await self._request(self._master.write_mask, device_id,
                                   address, and_mask, or_mask)

    async def _request(self, fn, *args):
        for retry_count in range(self._conf['request_retry_count']):
            with contextlib.suppres(asyncio.TimeoutError):
                result = await asyncio.wait_for(
                    fn(*args), self._conf['request_timeout'])

                if isinstance(result, modbus.Error):
                    return Error[result]

                return result

            if retry_count + 1 != self._conf['request_retry_count']:
                await self._conf['request_retry_delay']

        return Error.TIMEOUT
