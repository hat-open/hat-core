import asyncio
import contextlib
import logging

from hat import aio
from hat.gateway import common
from hat.gateway.devices.modbus.master.connection import connect
from hat.gateway.devices.modbus.master.event_client import (RemoteDeviceEnableReq,  # NOQA
                                                            RemoteDeviceWriteReq,  # NOQA
                                                            StatusRes,
                                                            RemoteDeviceStatusRes,  # NOQA
                                                            RemoteDeviceWriteRes,  # NOQA
                                                            EventClientProxy)
from hat.gateway.devices.modbus.master.remote_device import (RemoteDevice,
                                                             RemoteDeviceReader)  # NOQA
import hat.event.common


mlog = logging.getLogger(__name__)


async def create(conf: common.DeviceConf,
                 event_client: common.DeviceEventClient,
                 event_type_prefix: common.EventTypePrefix
                 ) -> 'ModbusMasterDevice':
    device = ModbusMasterDevice()
    device._enabled_devices = await _query_enabled_devices(event_client,
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

                    if device.device_id in self._enabled_devices:
                        self._device_readers[device.device_id] = \
                            RemoteDeviceReader(device, self._on_response)

                    else:
                        self._notify_response(RemoteDeviceStatusRes(
                            device_id=device.device_id,
                            status='DISABLED'))

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
        self._event_client.write([response])

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
            RemoteDeviceReader(device, self._notify_response)

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


async def _query_enabled_devices(event_client, event_type_prefix):
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
