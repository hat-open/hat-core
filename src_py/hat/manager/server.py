"""Web server and generic functionality"""

from pathlib import Path
import asyncio
import enum
import functools
import itertools
import logging
import time
import urllib

from hat import aio
from hat import json
from hat import juggler
from hat.manager import common
from hat.manager import devices


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

autoflush_delay: float = 0.2
"""Juggler autoflush delay"""

log_size: int = 100
"""Max log size"""

autostart_delay: float = 1
"""Auto start timeout"""


async def create_server(conf: json.Data,
                        conf_path: Path,
                        ui_path: Path
                        ) -> 'Server':
    """Create server

    Args:
        conf: configuration defined by ``hat://manager/main.yaml#``
        conf_path: configuration file path
        ui_path: static web ui frontent directory path

    """
    addr = urllib.parse.urlparse(conf['settings']['ui']['address'])

    server = Server()
    server._conf_path = conf_path
    server._devices = {}
    server._next_device_ids = (str(i) for i in itertools.count(1))
    server._data = common.DataStorage({'log': [],
                                       'devices': {},
                                       'settings': conf['settings']})

    server._srv = await juggler.listen(host=addr.hostname,
                                       port=addr.port,
                                       connection_cb=server._on_connection,
                                       static_dir=ui_path,
                                       autoflush_delay=autoflush_delay)

    server._logger = common.Logger()
    handler = server._logger.register_log_cb(server._on_log)
    server.async_group.spawn(aio.call_on_cancel, handler.cancel)

    for device_conf in conf['devices']:
        server._create_device(device_conf)

    return server


class Server(aio.Resource):
    """Manager server"""

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._srv.async_group

    def _on_log(self, msg):
        self._data.set('log', [{'timestamp': time.time(),
                                'message': msg},
                               *self._data.data['log']][:log_size])

    def _on_connection(self, conn):
        conn = juggler.RpcConnection(conn, {
            'set_settings': self._rpc_set_settings,
            'save': self._rpc_save,
            'add': self._rpc_add,
            'remove': self._rpc_remove,
            'start': self._rpc_start,
            'stop': self._rpc_stop,
            'set_name': self._rpc_set_name,
            'set_autostart': self._rpc_set_autostart,
            'execute': self._rpc_execute})
        conn.async_group.spawn(self._connection_loop, conn)

    async def _connection_loop(self, conn):
        try:
            changes = aio.Queue()
            with self._data.register_change_cb(changes.put_nowait):
                changes.put_nowait(self._data.data)
                while True:
                    data = await changes.get()
                    conn.set_local_data(data)

        except Exception as e:
            mlog.error("connection loop error: %s", e, exc_info=e)

        finally:
            conn.close()

    async def _device_loop(self, device_id, conf):
        device = _ProxyDevice(conf, self._logger)
        try:
            self._devices[device_id] = device
            on_change = functools.partial(self._data.set,
                                          ['devices', device_id])
            with device.data.register_change_cb(on_change):
                on_change(device.data.data)
                await device.wait_closing()

        except Exception as e:
            mlog.error("device loop error: %s", e, exc_info=e)

        finally:
            self._data.remove(['devices', device_id])
            del self._devices[device_id]
            await aio.uncancellable(device.async_close())

    def _rpc_set_settings(self, path, value):
        self._logger.log(f'configuration change ({path}: {value})')
        self._data.set(['settings', path], value)

    def _rpc_save(self):
        conf = dict(common.default_conf,
                    log=common.get_log_conf(self._data.data['settings']),
                    settings=self._data.data['settings'],
                    devices=[device.get_conf()
                             for device in self._devices.values()])
        self._conf_path.parent.mkdir(parents=True, exist_ok=True)
        json.encode_file(conf, self._conf_path)
        self._logger.log('configuration saved')

    def _rpc_add(self, device_type):
        return self._create_device(dict(devices.get_default_conf(device_type),
                                        type=device_type,
                                        name='New device',
                                        autostart=False))

    def _rpc_remove(self, device_id):
        device = self._devices[device_id]
        device.close()

    def _rpc_start(self, device_id):
        device = self._devices[device_id]
        device.start()

    def _rpc_stop(self, device_id):
        device = self._devices[device_id]
        device.stop()

    def _rpc_set_name(self, device_id, name):
        device = self._devices[device_id]
        device.set_name(name)

    def _rpc_set_autostart(self, device_id, autostart):
        device = self._devices[device_id]
        device.set_autostart(autostart)

    async def _rpc_execute(self, device_id, action, *args):
        device = self._devices[device_id]
        return await device.execute(action, *args)

    def _create_device(self, conf):
        device_id = next(self._next_device_ids)
        self.async_group.spawn(self._device_loop, device_id, conf)
        return device_id


class _Status(enum.Enum):
    STOPPED = 'stopped'
    STARTING = 'starting'
    STARTED = 'started'
    STOPPING = 'stopping'


class _ProxyDevice(aio.Resource):

    def __init__(self,
                 conf: json.Data,
                 logger: common.Logger):
        self._logger = logger
        self._async_group = aio.Group()
        self._run_subgroup = self.async_group.create_subgroup()
        self._autostart_subgroup = self.async_group.create_subgroup()

        device_logger = common.Logger()
        handler = device_logger.register_log_cb(self._log)
        self._async_group.spawn(aio.call_on_cancel, handler.cancel)

        self._device = devices.create_device(conf, device_logger)
        self._data = common.DataStorage({'type': conf['type'],
                                         'name': conf['name'],
                                         'autostart': conf['autostart'],
                                         'status': _Status.STOPPED.value,
                                         'data': self._device.data.data})

        on_change = functools.partial(self._data.set, 'data')
        handler = self._device.data.register_change_cb(on_change)
        self._async_group.spawn(aio.call_on_cancel, handler.cancel)

        self._log('device created')
        self._async_group.spawn(aio.call_on_cancel, self._log,
                                'removing device')

        if self._data.data['autostart']:
            self._run_autostart()

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    @property
    def data(self) -> common.DataStorage:
        return self._data

    def get_conf(self) -> json.Data:
        return dict(self._device.get_conf(),
                    type=self._data.data['type'],
                    name=self._data.data['name'],
                    autostart=self._data.data['autostart'])

    def start(self):
        previous = self._run_subgroup
        previous.close()
        self._run_subgroup = self._async_group.create_subgroup()
        self._run_subgroup.spawn(self._run, previous, self._run_subgroup)

    def stop(self):
        self._run_subgroup.close()

    def set_name(self, name: str):
        self._log(f'changing name to {name}')
        self._data.set('name', name)

    def set_autostart(self, autostart: bool):
        previous_autostart = self._data.data['autostart']
        if previous_autostart == autostart:
            return

        if autostart:
            self._run_autostart()
        else:
            self._autostart_subgroup.close()

        self._log(f'setting auto start {autostart}')
        self._data.set('autostart', autostart)

    async def execute(self,
                      action: str,
                      *args: json.Data
                      ) -> json.Data:
        return await self._device.execute(action, *args)

    def _log(self, msg):
        self._logger.log(f"{self._data.data['name']}: {msg}")

    async def _run(self, previous_subgroup, current_subgroup):
        resource = None
        try:
            await previous_subgroup.async_close()
            del previous_subgroup

            self._log('starting')
            self._data.set('status', _Status.STARTING.value)

            resource = await self._device.create()

            self._data.set('status', _Status.STARTED.value)
            self._log('started')

            await resource.wait_closing()

        except Exception as e:
            mlog.error("run loop error: %s", e, exc_info=e)

        finally:
            current_subgroup.close()
            await aio.uncancellable(self._close_resource(resource))

    def _run_autostart(self):
        previous_group = self._autostart_subgroup
        previous_group.close()
        self._autostart_subgroup = self._async_group.create_subgroup()
        self._autostart_subgroup.spawn(self._autostart_loop,
                                       previous_group,
                                       self._autostart_subgroup)

    async def _autostart_loop(self, previous_subgroup, current_subgroup):
        try:
            await previous_subgroup.async_close()
            del previous_subgroup

            if self._data.data['status'] == _Status.STOPPED.value:
                self.start()
            queue = aio.Queue()
            with self._data.register_change_cb(queue.put_nowait):
                while True:
                    state = await queue.get_until_empty()
                    if state['status'] != _Status.STOPPED.value:
                        continue
                    await asyncio.sleep(autostart_delay)
                    if self._data.data['status'] != _Status.STOPPED.value:
                        continue
                    self.start()

        except Exception as e:
            mlog.error("autostart loop error: %s", e, exc_info=e)

        finally:
            current_subgroup.close()

    async def _close_resource(self, resource):
        if resource:
            self._log('stopping')
            self._data.set('status', _Status.STOPPING.value)
            await resource.async_close()

        self._data.set('status', _Status.STOPPED.value)
        self._log('stopped')
