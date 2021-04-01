from pathlib import Path
import enum
import functools
import logging
import time
import typing
import urllib

from hat import aio
from hat import json
from hat import juggler
from hat import util

from hat.manager import common
from hat.manager import devices


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

autoflush_delay: float = 0.2
"""Juggler autoflush delay"""

log_size: int = 100
"""Max log size"""


async def create_server(conf: json.Data,
                        conf_path: Path,
                        ui_path: Path
                        ) -> 'Server':
    """Create server"""
    addr = urllib.parse.urlparse(conf['settings']['ui']['address'])

    server = Server()
    server._conf_path = conf_path
    server._logger = _Logger()
    server._devices = {}
    server._last_device_id = 0
    server._change_cbs = util.CallbackRegistry(lambda _: None)
    server._data = {'log': server._logger.data,
                    'devices': {},
                    'settings': conf['settings']}

    server._srv = await juggler.listen(host=addr.hostname,
                                       port=addr.port,
                                       connection_cb=server._on_connection,
                                       static_dir=ui_path,
                                       autoflush_delay=autoflush_delay)

    on_change = functools.partial(server._set, 'log')
    handler = server._logger.register_change_cb(on_change)
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

    def _on_connection(self, conn):
        conn = juggler.RpcConnection(conn, {
            'set_settings': self._rpc_set_settings,
            'save': self._rpc_save,
            'add': self._rpc_add,
            'remove': self._rpc_remove,
            'start': self._rpc_start,
            'stop': self._rpc_stop,
            'set_name': self._rpc_set_name,
            'set_auto_start': self._rpc_set_auto_start,
            'execute': self._rpc_execute})
        self.async_group.spawn(self._connection_loop, conn)

    async def _connection_loop(self, conn):
        try:
            with self._change_cbs.register(conn.set_local_data):
                conn.set_local_data(self._data)
                await conn.wait_closing()

        except Exception as e:
            mlog.error("connection loop error: %s", e, exc_info=e)

        finally:
            await aio.uncancellable(conn.async_close())

    async def _device_loop(self, device_id, conf):
        device = _ProxyDevice(conf, self._logger)
        try:
            self._devices[device_id] = device
            on_change = functools.partial(self._set, ['devices', device_id])
            with device.register_change_cb(on_change):
                on_change(device.data)
                await device.wait_closing()

        except Exception as e:
            mlog.error("device loop error: %s", e, exc_info=e)

        finally:
            self._remove(['devices', device_id])
            del self._devices[device_id]
            await aio.uncancellable(device.async_close())

    def _rpc_set_settings(self, path, value):
        self._logger.log(f'configuration change ({path}: {value})')
        self._set(['settings', path], value)

    def _rpc_save(self):
        conf = dict(common.default_conf,
                    log=common.get_log_conf(self._data['settings']),
                    settings=self._data['settings'],
                    devices=[device.get_conf()
                             for device in self._devices.values()])
        self._conf_path.parent.mkdir(parents=True, exist_ok=True)
        json.encode_file(conf, self._conf_path)
        self._logger.log('configuration saved')

    def _rpc_add(self, device_type):
        return self._create_device(dict(devices.get_default_conf(device_type),
                                        type=device_type,
                                        name='New device',
                                        auto_start=False))

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

    def _rpc_set_auto_start(self, device_id, auto_start):
        device = self._devices[device_id]
        device.set_auto_start(auto_start)

    async def _rpc_execute(self, device_id, action, *args):
        device = self._devices[device_id]
        return await device.execute(action, *args)

    def _create_device(self, conf):
        self._last_device_id += 1
        device_id = str(self._last_device_id)
        self.async_group.spawn(self._device_loop, device_id, conf)
        return device_id

    def _set(self, path, value):
        self._data = json.set_(self._data, path, value)
        self._change_cbs.notify(self._data)

    def _remove(self, path):
        self._data = json.remove(self._data, path)
        self._change_cbs.notify(self._data)


class _Logger:

    def __init__(self):
        self._data = []
        self._change_cbs = util.CallbackRegistry()

    @property
    def data(self) -> json.Data:
        return self._data

    def register_change_cb(self,
                           cb: typing.Callable[[json.Data], None]
                           ) -> util.RegisterCallbackHandle:
        return self._change_cbs.register(cb)

    def log(self, msg: str):
        self._data = [{'timestamp': time.time(),
                       'message': msg},
                      *self._data][:log_size]
        self._change_cbs.notify(self._data)


class _Status(enum.Enum):
    STOPPED = 'stopped'
    STARTING = 'starting'
    STARTED = 'started'
    STOPPING = 'stopping'


class _ProxyDevice(aio.Resource):

    def __init__(self,
                 conf: json.Data,
                 logger: common.Logger):
        self._logger = _ProxyLogger(self, logger)
        self._device = devices.create_device(conf, self._logger)
        self._data = {'type': conf['type'],
                      'name': conf['name'],
                      'auto_start': conf['auto_start'],
                      'status': _Status.STOPPED.value,
                      'data': self._device.data}
        self._change_cbs = util.CallbackRegistry()
        self._subgroup = self.async_group.create_subgroup()

        on_change = functools.partial(self._set, 'data')
        handler = self._device.register_change_cb(on_change)
        self.async_group.spawn(aio.call_on_cancel, handler.cancel)

        self._logger.log('device created')
        self.async_group.spawn(aio.call_on_cancel, self._logger.log,
                               'removing device')

    @property
    def async_group(self) -> aio.Group:
        return self._device.async_group

    @property
    def data(self) -> json.Data:
        return self._data

    def register_change_cb(self,
                           cb: typing.Callable[[json.Data], None]
                           ) -> util.RegisterCallbackHandle:
        return self._change_cbs.register(cb)

    def get_conf(self) -> json.Data:
        return dict(self._device.get_conf(),
                    type=self._data['type'],
                    name=self._data['name'],
                    auto_start=self._data['auto_start'])

    def start(self):
        previous = self._subgroup
        self._subgroup = self.async_group.create_subgroup()
        self._subgroup.spawn(self._run, previous, self._subgroup)

    def stop(self):
        self._subgroup.close()

    def set_name(self, name: str):
        self._logger.log(f'changing name to {name}')
        self._set('name', name)

    def set_auto_start(self, auto_start: str):
        self._logger.log(f'setting auto start {auto_start}')
        self._set('auto_start', auto_start)

    async def execute(self,
                      action: str,
                      *args: json.Data
                      ) -> json.Data:
        return await self._device.execute(action, *args)

    async def _run(self, previous_subgroup, current_subgroup):
        resource = None
        try:
            await previous_subgroup.async_close()
            del previous_subgroup

            self._logger.log('starting')
            self._set('status', _Status.STARTING.value)

            resource = await self._device.create()

            self._set('status', _Status.STARTED.value)
            self._logger.log('started')

            await resource.wait_closing()

        except Exception as e:
            mlog.error("run loop error: %s", e, exc_info=e)

        finally:
            current_subgroup.close()
            await aio.uncancellable(self._close_resource(resource))

    async def _close_resource(self, resource):
        if resource:
            self._logger.log('stopping')
            self._set('status', _Status.STOPPING.value)
            await resource.async_close()

        self._set('status', _Status.STOPPED.value)
        self._logger.log('stopped')

    def _set(self, path, value):
        self._data = json.set_(self._data, path, value)
        self._change_cbs.notify(self._data)


class _ProxyLogger(common.Logger):

    def __init__(self, device: _ProxyDevice, logger: _Logger):
        self._device = device
        self._logger = logger

    def log(self, msg: str):
        self._logger.log(f"{self._device._data['name']}: {msg}")
