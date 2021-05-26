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

    device._async_group.spawn(aio.call_on_cancel,
                              device._event_client.async_close)
    device._async_group.spawn(device._event_client_loop)
    device._async_group.spawn(device._connection_loop)
    return device


class ModbusMasterDevice(aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    async def _event_client_loop(self):
        try:
            mlog.debug('starting event client loop')
            while True:
                request = await self._event_client.read()

                if isinstance(request, RemoteDeviceEnableReq):
                    mlog.debug('received remote device enable request')
                    if request.enable:
                        self._enable_remote_device(request.device_id)
                    else:
                        await self._disable_remote_device(request.device_id)

                elif isinstance(request, RemoteDeviceWriteReq):
                    mlog.debug('received remote device write request')
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
            mlog.debug('closing event client loop')
            self.close()

    async def _connection_loop(self):
        try:
            mlog.debug('starting connection loop')
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
                self._devices = {}
                self._device_readers = {}

                mlog.debug('creating remote devices')
                for device_conf in self._conf['remote_devices']:
                    device = RemoteDevice(device_conf, self._conn)
                    self._devices[device.device_id] = device

                    if device.device_id in self._enabled_devices:
                        self._enable_remote_device(device.device_id)
                    else:
                        self._notify_response(RemoteDeviceStatusRes(
                            device_id=device.device_id,
                            status='DISABLED'))

                await self._conn.wait_closing()
                await self._conn.async_close()
                self._set_status('DISCONNECTED')

        except Exception as e:
            mlog.error('connection loop error: %s', e, exc_info=e)

        finally:
            mlog.debug('closing connection loop')
            self.close()
            if self._conn:
                await aio.uncancellable(self._conn.async_close())
            self._set_status('DISCONNECTED')

    def _notify_response(self, response):
        self._event_client.write([response])

    def _set_status(self, status):
        if self._status == status:
            return
        mlog.debug('changing status: %s -> %s', self._status, status)
        self._status = status
        self._notify_response(StatusRes(status))

    def _enable_remote_device(self, device_id):
        mlog.debug('enabling device %s', device_id)
        self._enabled_devices.add(device_id)

        device = self._devices.get(device_id)
        if not device:
            mlog.debug('device %s is not available', device_id)
            return
        if not device.conn.is_open:
            mlog.debug('connection is not available')
            return

        device_reader = self._device_readers.get(device_id)
        if device_reader and device_reader.is_open:
            mlog.debug('device reader %s is already running', device_id)
            return

        mlog.debug('creating reader for device %s', device_id)
        self._device_readers[device.device_id] = \
            RemoteDeviceReader(device, self._notify_response)

    async def _disable_remote_device(self, device_id):
        mlog.debug('disabling device %s', device_id)
        self._enabled_devices.discard(device_id)

        device_reader = self._device_readers.pop(device_id, None)
        if not device_reader:
            mlog.debug('device reader %s is not available', device_id)
            return

        await device_reader.async_close()

    async def _write(self, device_id, data_name, request_id, value):
        mlog.debug('writing (device_id: %s; data_name: %s; value: %s)',
                   device_id, data_name, value)

        device = self._devices.get(device_id)
        if not device:
            mlog.debug('device %s is not available', device_id)
            return

        data = device.data.get(data_name)
        if not data:
            mlog.debug('data %s is not available', data_name)
            return

        result = await data.write(value)
        result = result.name if result else 'SUCCESS'
        mlog.debug('writing result: %s', result)
        self._notify_response(RemoteDeviceWriteRes(device_id=device_id,
                                                   data_name=data_name,
                                                   request_id=request_id,
                                                   result=result))


async def _query_enabled_devices(event_client, event_type_prefix):
    mlog.debug('querying enabled devices')
    enabled_devices = set()

    events = await event_client.query(hat.event.common.QueryData(
        event_types=[(*event_type_prefix, 'system', 'remote_device', '?',
                      'enable')],
        unique_type=True))
    mlog.debug('received %s events', len(events))

    for event in events:
        if not event.payload or not bool(event.payload.data):
            continue

        device_id_str = event.event_type[6]
        with contextlib.suppress(ValueError):
            enabled_devices.add(int(device_id_str))

    mlog.debug('detected %s enabled devices', len(enabled_devices))
    return enabled_devices
