import math
import itertools
import asyncio
import typing

from hat import aio
from hat import json
from hat.drivers import modbus
from hat.gateway.devices.modbus.master.connection import Error
from hat.gateway.devices.modbus.master.event_client import (RemoteDeviceReadRes, Connection, Response)  # NOQA


ResponseCb = typing.Callable[[Response], None]


class Data:

    def __init__(self,
                 conf: json.Data,
                 device_id: int,
                 conn: Connection):
        self._conf = conf
        self._device_id = device_id
        self._conn = conn
        self._data_type = modbus.DataType[conf['data_type']]
        self._register_size = _get_register_size(self._data_type)
        self._start_address = conf['start_address']
        self._bit_count = conf['bit_count']
        self._start_bit = conf['start_bit']
        self._quantity = math.cail((self._bit_count + self._start_bit) /
                                   self._register_size)

    async def write(self, value: int) -> typing.Optionaln[Error]:
        pass

    async def read(self) -> typing.Union[int, Error]:
        result = await self._conn.read(self._device_id, self._data_type,
                                       self._start_address, self._quantity)
        if isinstance(result, Error):
            return result
        return _get_registers_value(self._register_size, self._start_bit,
                                    self._bit_count, result)


class DataReader(aio.Resource):

    def __init__(self, data: Data, response_cb: ResponseCb):
        self._data = data
        self._response_cb = response_cb
        self._device_id = data._device_id
        self._name = data._conf['name']
        self._interval = data._conf['interval']
        self._async_group = data._conn.async_group.create_subgroup()
        self._last_response = None

        if self._interval is not None:
            self._async_group.spawn(self._read_loop)

    @property
    def async_group(self):
        return self._async_group

    @property
    def is_connected(self) -> bool:
        if self.is_closing:
            return False
        if self._interval is None:
            return True
        return bool(self._last_response and
                    self._last_response.result != 'TIMEOUT')

    async def _read_loop(self):
        try:
            while True:
                result = await self._data.read()

                if isinstance(result, Error):
                    response = self._create_response(
                        result.name, None, None)

                elif (self._last_response is None or
                        self._last_response.result != 'SUCCESS'):
                    response = self._create_response(
                        'SUCCESS', result, 'INTERROGATE')

                elif self._last_response.value != result:
                    response = self._create_response(
                        'SUCCESS', result, 'CHANGE')

                else:
                    response = None

                if response:
                    self._last_response = response
                    self._response_cb(response)

                await asyncio.sleep(self._interval)

        finally:
            self.close()

    def _create_response(self, result, value, cause):
        return RemoteDeviceReadRes(
            device_id=self._device_id,
            data_name=self._name,
            result=result,
            value=value,
            cause=cause)


def _get_register_size(data_type):
    if data_type in (modbus.DataType.COIL,
                     modbus.DataType.DISCRETE_INPUT):
        return 1

    if data_type in (modbus.DataType.HOLDING_REGISTER,
                     modbus.DataType.INPUT_REGISTER,
                     modbus.DataType.QUEUE):
        return 16

    raise ValueError('invalid data type')


def _get_registers_value(register_size, start_bit, bit_count, values):
    result = 0
    bits = itertools.chain(_get_registers_bits(register_size, values),
                           itertools.repeat(0))
    for i in itertools.islice(bits, start_bit, start_bit + bit_count):
        result = (result << 1) | i
    return result


def _get_registers_bits(register_size, values):
    for value in values:
        for i in range(register_size):
            yield (value >> (register_size - i - 1)) & 1
