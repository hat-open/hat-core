import collections

from hat import aio
from hat import json
from hat.gateway.devices.modbus.master.connection import Connection
from hat.gateway.devices.modbus.master.data import (Data, DataReader, ResponseCb)  # NOQA
from hat.gateway.devices.modbus.master.event_client import RemoteDeviceStatusRes  # NOQA


class RemoteDevice:

    def __init__(self,
                 conf: json.Data,
                 conn: Connection):
        self._conn = conn
        self._device_id = conf['device_id']
        self._data = {i['name']: Data(i, self._device_id, conn)
                      for i in conf['data']}

    @property
    def device_id(self) -> int:
        return self._device_id

    @property
    def data(self):
        return self._data


class RemoteDeviceReader(aio.Resource):

    def __init__(self, remote_device, response_cb):
        self._response_cb = response_cb
        self._device_id = remote_device._device_id
        self._async_group = remote_device._conn.async_group.create_subgroup()
        self._status = None
        self._data_readers = collections.deque()

        for data in remote_device._data.values():
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
    def async_group(self):
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
