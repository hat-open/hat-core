import enum
import typing

from hat import aio
from hat import json
from hat import util


_last_device_id = 0


Status = enum.Enum('Status', [
    'STOPPED',
    'STARTING',
    'STARTED',
    'STOPPING'])


class Master(aio.Resource):

    def __init__(self, log):
        global _last_device_id
        _last_device_id += 1

        self._async_group = aio.Group()
        self._subgroup = self._async_group.create_subgroup()
        self._conn = None
        self._device_id = _last_device_id
        self._change_cbs = util.CallbackRegistry()
        self._data = {'type': 'master',
                      'status': 'STOPPED',
                      'properties': {'name': f'Master {self._device_id}',
                                     'host': '127.0.0.1',
                                     'port': 2404,
                                     'response_timeout': 15,
                                     'supervisory_timeout': 10,
                                     'test_timeout': 20,
                                     'send_window_size': 12,
                                     'receive_window_size': 8},
                      'data': []}

        self._log = lambda msg: log.log(f"{self._data['name']}: {msg}")
        self._log('created')

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    @property
    def device_id(self) -> int:
        self._device_id

    @property
    def data(self) -> json.Data:
        return self._data

    def register_change_cb(self,
                           cb: typing.Callable[[json.Data], None]
                           ) -> util.RegisterCallbackHandle:
        return self._change_cbs.register(cb)

    def start(self):
        previous = self._subgroup
        self._subgroup = self._async_group.create_subgroup()
        self._subgroup.spawn(self._connection_loop, previous,
                             self._data['properties'])

    def stop(self):
        self._subgroup.close()

    def interrogate(self, asdu):
        self._subgroup.spawn(self._interrogate, self._conn, asdu)

    def send_command(self, cmd):
        self._subgroup.spawn(self._send_command, self._conn, cmd)

    def set_property(self, key, value):
        self._log(f"changing {key} {self._data['properties'][key]} -> {value}")
        self._set(['properties', key], value)

    def _set(self, path, value):
        self._data = json.set_(self._data, path, value)
        self._change_cbs.notify(self._data)

    async def _connection_loop(self, previous, properties):
        pass

    async def _interrogate(self, conn, asdu):
        pass

    async def _send_command(self, conn, cmd):
        pass
