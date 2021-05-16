import asyncio
import collections
import contextlib
import itertools
import logging
import math
import typing

from hat import aio
from hat import json
from hat.gateway import common
from hat.gateway.devices.modbus.master.connection import (DataType,
                                                          Error,
                                                          connect,
                                                          Connection)
from hat.gateway.devices.modbus.master.event_client import (RemoteDeviceEnableReq,  # NOQA
                                                            RemoteDeviceWriteReq,  # NOQA
                                                            Request,
                                                            StatusRes,
                                                            RemoteDeviceStatusRes,  # NOQA
                                                            RemoteDeviceReadRes,  # NOQA
                                                            RemoteDeviceWriteRes,  # NOQA
                                                            Response,
                                                            EventClientProxy)
import hat.event.common


mlog = logging.getLogger(__name__)


ResponseCb = typing.Callable[[Response], None]


async def create(conf: common.DeviceConf,
                 event_client: common.DeviceEventClient,
                 event_type_prefix: common.EventTypePrefix
                 ) -> 'ModbusMasterDevice':
    device = ModbusMasterDevice()
    device._enabled_devices = await query_enabled_devices(event_client,
                                                          event_type_prefix)
    device._conf = conf
    device._event_client = EventClientProxy(event_client, event_type_prefix)
    device._status = None
    device._conn = None
    device._devices = {}
    device._device_readers = {}
    device._async_group = aio.Group()

    device._async_group.spawn(device._event_client_loop)
    device._async_group.spawn(device._connection_loop)
    return device


async def query_enabled_devices(event_client, event_type_prefix):
    enabled_devices = set()

    events = await event_client.query(hat.event.common.QueryData(
        event_types=[(*event_type_prefix, 'system', 'remote_device', '?',
                      'enable')],
        unique_type=True))

    for event in events:
        if not event.payload or not bool(event.payload.data):
            continue

        device_id_str = event.event_type[6]
        with contextlib.suppress:
            enabled_devices.add(int(device_id_str))

    return enabled_devices


class ModbusMasterDevice(aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    async def _event_client_loop(self):
        try:
            while True:
                request = await self._event_client.read()

                if isinstance(request, RemoteDeviceEnableReq):
                    if request.enable:
                        self._enable_remote_device(request.device_id)
                    else:
                        self._disable_remote_device(request.device_id)

                elif isinstance(request, RemoteDeviceWriteReq):
                    if self._conn and self._conn.is_open:
                        self._conn.async_group.spawn(
                            self._write, request.device_id, request.data_name,
                            request.request_id, request.value)

                else:
                    raise ValueError('invalid request')

        except ConnectionError:
            mlog.debug('event client connection closed')

        except Exception as e:
            mlog.error('event client loop error: %s', e, exc_info=e)

        finally:
            self.close()

    async def _connection_loop(self):
        try:
            while True:
                self._set_status('CONNECTING')

                try:
                    self._conn = await aio.wait_for(
                        connect(self._conf['connection']),
                        self._conf['connection']['connect_timeout'])
                except aio.CancelledWithResultError as e:
                    self._conn = e.result
                    raise
                except Exception as e:
                    mlog.info('connecting error: %s', e, exc_info=e)
                    self._set_status('DISCONNECTED')
                    await asyncio.sleep(
                        self._conf['connection']['connect_delay'])
                    continue

                self._set_status('CONNECTED')

                for device_conf in self._conf['remote_devices']:
                    device = RemoteDevice(device_conf, self._conn)
                    self._devices[device.device_id] = device
                    if device.device_id in device._enabled_devices:
                        self._device_readers[device.device_id] = \
                            RemoteDeviceReader(device, self._on_response)

                await self._conn.wait_closing()

                self._devices = {}
                self._device_readers = {}
                self._set_status('DISCONNECTED')

                await self._conn.async_close()

        except Exception as e:
            mlog.error('connection loop error: %s', e, exc_info=e)

        finally:
            self.close()
            if self._conn:
                await aio.uncancellable(self._conn.async_close())
            self._set_status('DISCONNECTED')

    def _notify_response(self, response):
        pass

    def _set_status(self, status):
        if self._status == status:
            return
        self._status = status
        self._notify_response(StatusRes(status))

    def _enable_remote_device(self, device_id):
        if device_id in self._enabled_devices:
            return

        self._enabled_devices.add(device_id)
        device = self._devices.get(device_id)
        if not device:
            return

        self._device_readers[device.device_id] = \
            RemoteDeviceReader(device, self._on_response)

    def _disable_remote_device(self, device_id):
        if device_id not in self._enabled_devices:
            return

        self._enabled_devices.remove(device_id)
        device_reader = self._device_readers.pop(device_id, None)
        if not device_reader:
            return

        device_reader.close()

    async def _write(self, device_id, data_name, request_id, value):
        device = self._devices.get(device_id)
        if not device:
            return

        data = device.data.get(data_name)
        if not data:
            return

        result = await data.write(value)
        result = result.name if result else 'SUCCESS'
        self._notify_response(RemoteDeviceWriteRes(device_id=device_id,
                                                   data_name=data_name,
                                                   request_id=request_id,
                                                   result=result))


class RemoteDevice:

    def __init__(self,
                 conf: json.Data,
                 conn: Connection):
        self._conn = conn
        self._device_id = conf['device_id']
        self._data = {i['name']: Data(i, self._device_id, conn)
                      for i in conf['data']}

    @property
    def conn(self) -> Connection:
        return self._conn

    @property
    def device_id(self) -> int:
        return self._device_id

    @property
    def data(self) -> typing.Dict[int, 'Data']:
        return self._data


class RemoteDeviceReader(aio.Resource):

    def __init__(self,
                 remote_device: RemoteDevice,
                 response_cb: ResponseCb):
        self._response_cb = response_cb
        self._device_id = remote_device.device_id
        self._async_group = remote_device.conn.async_group.create_subgroup()
        self._status = None
        self._data_readers = collections.deque()

        for data in remote_device.data.values():
            data_reader = DataReader(data, self._on_response)
            self._async_group.spawn(aio.call_on_cancel,
                                    data_reader.async_close)
            self._async_group.spawn(aio.call_on_done,
                                    data_reader.wait_closing(),
                                    self._async_group.close)
            self._data_readers.append(data_reader)

        self._set_status('DISCONNECTED')
        self._async_group.spawn(aio.call_on_cancel, self._set_status,
                                'DISCONNECTED')

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    def _on_response(self, res):
        self._on_response(res)
        is_connected = all(i.is_connected for i in self._data_readers)
        self._set_status('CONNECTED' if is_connected else 'DISCONNECTED')

    def _set_status(self, status):
        if self._status == status:
            return
        self._status = status
        self._response_cb(RemoteDeviceStatusRes(device_id=self._device_id,
                                                status=status))


class Data:

    def __init__(self,
                 conf: json.Data,
                 device_id: int,
                 conn: Connection):
        self._device_id = device_id
        self._conn = conn
        self._data_type = DataType[conf['data_type']]
        self._register_size = _get_register_size(self._data_type)
        self._start_address = conf['start_address']
        self._bit_count = conf['bit_count']
        self._start_bit = conf['start_bit']
        self._quantity = math.ceil((self._bit_count + self._start_bit) /
                                   self._register_size)
        self._interval = conf['interval']
        self._name = conf['name']

    @property
    def conn(self) -> Connection:
        return self._conn

    @property
    def interval(self):
        return self._interval

    @property
    def name(self):
        return self._name

    @property
    def device_id(self):
        return self._device_id

    async def write(self, value: int) -> typing.Optional[Error]:
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
        self._device_id = data.device_id
        self._name = data.name
        self._interval = data.interval
        self._async_group = data.conn.async_group.create_subgroup()
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
    if data_type in (DataType.COIL,
                     DataType.DISCRETE_INPUT):
        return 1

    if data_type in (DataType.HOLDING_REGISTER,
                     DataType.INPUT_REGISTER,
                     DataType.QUEUE):
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
