import enum
import typing

from hat import aio
from hat import json
from hat import util


class Status(enum.Enum):
    STOPPED = 'stopped'
    STARTING = 'starting'
    STARTED = 'started'
    STOPPING = 'stopping'


class Device(aio.Resource):

    def __init__(self, name, log):
        self._async_group = aio.Group()
        self._subgroup = self._async_group.create_subgroup()
        self._change_cbs = util.CallbackRegistry()
        self._data = {'type': 'master',
                      'status': Status.STOPPED.value,
                      'properties': {'name': name,
                                     'host': '127.0.0.1',
                                     'port': 2404,
                                     'response_timeout': 15,
                                     'supervisory_timeout': 10,
                                     'test_timeout': 20,
                                     'send_window_size': 12,
                                     'receive_window_size': 8}}

        self._log = lambda msg: log.log(
            f"{self._data['properties']['name']}: {msg}")
        self._log('created')
        self._async_group.spawn(aio.call_on_cancel, self._log, 'removing')

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    @property
    def data(self) -> json.Data:
        return self._data

    def register_change_cb(self,
                           cb: typing.Callable[[json.Data], None]
                           ) -> util.RegisterCallbackHandle:
        return self._change_cbs.register(cb)

    def set_property(self, key, value):
        self._log(f"changing {key} {self._data['properties'][key]} -> {value}")
        self._set(['properties', key], value)

    def start(self):
        previous = self._subgroup
        self._subgroup = self._async_group.create_subgroup()
        self._subgroup.spawn(self._run, previous)

    def stop(self):
        self._subgroup.close()

    async def _run(self, previous):
        try:
            await previous.async_close()
            del previous
            await self._device_loop()
        finally:
            self._subgroup.close()

    def _set(self, path, value):
        self._data = json.set_(self._data, path, value)
        self._change_cbs.notify(self._data)

    def _change_status(self, status):
        self._log(f"changing status {self._data['status']} -> {status.value}")
        self._set('status', status.value)


class Master(Device):

    def __init__(self, name, log):
        super().__init__(name, log)

        self._data['data'] = []

    def interrogate(self, asdu):
        self._subgroup.spawn(self._interrogate, self._conn, asdu)

    def send_command(self, cmd):
        self._subgroup.spawn(self._send_command, self._conn, cmd)

    async def _device_loop(self):
        pass

    async def _interrogate(self, conn, asdu):
        pass

    async def _send_command(self, conn, cmd):
        pass


class Slave(Device):

    def __init__(self, name, log):
        super().__init__(name, log)

        self._data['master_count'] = 0
        self._data['data'] = {}
        self._data['commands'] = {}
        self._last_data_id = 0
        self._last_command_id = 0

    def add_data(self):
        self._last_data_id += 1
        data_id = str(self._last_data_id)
        self._log("adding new data")
        self._set(['data', data_id], {'properties': {'asdu': 0,
                                                     'io': 0,
                                                     'type': 'Single'},
                                      'value': None,
                                      'quality': None,
                                      'time': None,
                                      'cause': None,
                                      'is_test': None})

    def remove_data(self, data_id):
        self._log("removing data")
        data = dict(self._data['data'])
        del data[data_id]
        self._set('data', data)

    def set_data_property(self, data_id, key, value):
        path = ['data', data_id, key]
        previous = json.get(self._data, path)
        self._log(f"changing data {key} {previous} -> {value}")
        self._set(path, value)

    def add_command(self):
        self._last_command_id += 1
        command_id = str(self._last_command_id)
        self._log("adding new command")
        self._set(['commands', command_id], {'properties': {'asdu': 0,
                                                            'io': 0,
                                                            'type': 'Single',
                                                            'success': True},
                                             'action': None,
                                             'value': None,
                                             'time': None,
                                             'qualifier': None})

    def remove_command(self, command_id):
        self._log("removing command")
        commands = dict(self._data['commands'])
        del commands[command_id]
        self._set('commands', commands)

    def set_command_property(self, command_id, key, value):
        path = ['commands', command_id, key]
        previous = json.get(self._data, path)
        self._log(f"changing command {key} {previous} -> {value}")
        self._set(path, value)

    async def _device_loop(self):
        pass
