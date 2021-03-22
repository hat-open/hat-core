import contextlib
import functools

from hat import aio
from hat import util
from hat import json
from hat import juggler

from hat.manager.iec104 import common
import hat.manager.iec104.device


async def create_server(host, port, path):
    server = Server()
    server._log = common.Log()
    server._devices = {}
    server._last_device_id = 0
    server._change_cbs = util.CallbackRegistry()

    server._srv = await juggler.listen(host, port, server._on_connection,
                                       static_dir=path)

    server._data = {'devices': [],
                    'log': server._log.data}

    server.async_group.spawn(
        aio.call_on_cancel,
        server._log.register_change_cb(server._on_log_change).cancel)

    return server


class Server(aio.Resource):

    @property
    def async_group(self):
        return self._srv.async_group

    def _on_connection(self, conn):
        conn = juggler.RpcConnection(conn, {
            'create_master': self._act_create_master,
            'create_slave': self._act_create_slave,
            'remove_device': self._act_remove_device,
            'set_property': self._act_set_property,
            'start': self._act_start,
            'stop': self._act_stop,
            'interrogate': self._act_interrogate,
            'send_command': self._act_send_command,
            'add_data': self._act_add_data,
            'remove_data': self._act_remove_data,
            'set_data_property': self._act_set_data_property,
            'add_command': self._act_add_command,
            'remove_command': self._act_remove_command,
            'set_command_property': self._act_set_command_property})
        self.async_group.spawn(self._connection_loop, conn)

    def _on_log_change(self, data):
        self._set('log', data)

    def _on_device_change(self, device_id, data):
        self._set(['devices', device_id], data)

    async def _connection_loop(self, conn):
        try:
            with self._change_cbs.register(conn.set_local_data):
                conn.set_local_data(self._data)
                await conn.wait_closing()
        finally:
            await aio.uncancellable(conn.async_close())

    async def _device_loop(self, device_id, device):
        try:
            on_change = functools.partial(self._on_device_change, device_id)
            with device.register_change_cb(on_change):
                on_change(device.data)
                await device.wait_closing()
        finally:
            with contextlib.suppress(Exception):
                if device_id in self._data['devices']:
                    devices = dict(self._data['devices'])
                    del devices[device_id]
                    self._set('devices', devices)
            await aio.uncancellable(device.async_close())

    def _set(self, path, value):
        self._data = json.set_(self._data, path, value)
        self._change_cbs.notify(self._data)

    def _act_create_master(self):
        self._last_device_id += 1
        device_id = str(self._last_device_id)
        name = f'Master {device_id}'
        device = hat.manager.iec104.device.Master(name, self._log)
        self._devices[device_id] = device
        self.async_group.spawn(self._device_loop, device_id, device)

    def _act_create_slave(self):
        self._last_device_id += 1
        device_id = str(self._last_device_id)
        name = f'Slave {device_id}'
        device = hat.manager.iec104.device.Slave(name, self._log)
        self._devices[device_id] = device
        self.async_group.spawn(self._device_loop, device_id, device)

    def _act_remove_device(self, device_id):
        device = self._devices.pop(device_id)
        device.close()

    def _act_set_property(self, device_id, key, value):
        device = self._devices[device_id]
        device.set_property(key, value)

    def _act_start(self, device_id):
        device = self._devices[device_id]
        device.start()

    def _act_stop(self, device_id):
        device = self._devices[device_id]
        device.stop()

    def _act_interrogate(self, device_id, asdu):
        device = self._devices[device_id]
        device.interrogate(asdu)

    def _act_send_command(self, device_id, cmd):
        device = self._devices[device_id]
        device.send_command(cmd)

    def _act_add_data(self, device_id):
        device = self._devices[device_id]
        device.add_data()

    def _act_remove_data(self, device_id, data_id):
        device = self._devices[device_id]
        device.remove_data(data_id)

    def _act_set_data_property(self, device_id, data_id, key, value):
        device = self._devices[device_id]
        device.set_data_property(data_id, key, value)

    def _act_add_command(self, device_id):
        device = self._devices[device_id]
        device.add_command()

    def _act_remove_command(self, device_id, command_id):
        device = self._devices[device_id]
        device.remove_command(command_id)

    def _act_set_command_property(self, device_id, command_id, key, value):
        device = self._devices[device_id]
        device.set_command_property(command_id, key, value)
