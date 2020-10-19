import asyncio

from hat import juggler
from hat import util
from hat.util import aio
from hat.drivers import hue
from hat.drivers import upnp


async def create(ui_path):
    port = util.get_unused_tcp_port()

    srv = Server()
    srv._addr = f'http://127.0.0.1:{port}'
    srv._async_group = aio.Group()
    srv._srv = await juggler.listen('127.0.0.1', port, srv._on_connection,
                                    static_dir=ui_path)
    srv._async_group.spawn(aio.call_on_cancel, srv._srv.async_close)
    srv._async_group.spawn(aio.call_on_done, srv._srv.closed,
                           srv._async_group.close)
    return srv


class Server:

    @property
    def addr(self):
        return self._addr

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self):
        await self._async_close()

    def _on_connection(self, conn):
        Session(self._async_group.create_subgroup(), conn)


class Session:

    def __init__(self, async_group, juggler_conn):
        self._async_group = async_group
        self._juggler_conn = juggler_conn
        self._hue_conn = None
        self._rpc_cbs = {'find_hubs': self.find_hubs,
                         'create_user': self.create_user,
                         'connect': self.connect,
                         'disconnect': self.disconnect,
                         'get': self.get,
                         'set_conf': self.set_conf}

        async_group.spawn(aio.call_on_cancel, juggler_conn.async_close)
        async_group.spawn(aio.call_on_cancel, self.disconnect)
        async_group.spawn(aio.call_on_done, juggler_conn.closed,
                          async_group.close)
        async_group.spawn(self._session_loop)

    async def _session_loop(self):
        try:
            while True:
                msg = await self._juggler_conn.receive()
                rpc_cb = self._rpc_cbs[msg['action']]
                try:
                    result = await aio.call(rpc_cb, *msg['args'])
                    error = None
                except Exception as e:
                    result = None
                    error = str(e)
                await self._juggler_conn.send({
                    'transaction': msg['transaction'],
                    'result': result,
                    'error': error})
        except ConnectionError:
            pass
        finally:
            self._async_group.close()

    async def find_hubs(self, duration):
        available = {}
        locations = set()

        async def on_device_info(info):
            if (not info.server or
                    not info.location or
                    'IpBridge' not in info.server or
                    info.location in locations):
                return
            locations.add(info.location)
            desc = await upnp.get_description(info.location)
            if (not desc.model_name or
                    not desc.url or
                    'Philips hue bridge' not in desc.model_name):
                return
            url = desc.url if desc.url[-1] != '/' else desc.url[:-1]
            available[desc.url] = {'url': url,
                                   'name': desc.dev_name}

        srv = await upnp.discover(on_device_info)
        await asyncio.sleep(duration)
        await srv.async_close()
        return list(available.values())

    async def create_user(self, url, app_name, dev_name):
        return await hue.create_user(url, app_name, dev_name)

    async def connect(self, url, user):
        await self.disconnect()
        self._hue_conn = hue.Client(url, user)

    async def disconnect(self):
        if not self._hue_conn:
            return
        await self._hue_conn.async_close()
        self._hue_conn = None

    async def get(self, device_id):
        if not device_id:
            return await self._hue_conn.transport.get(None)
        return await self._hue_conn.transport.get(
            hue.DeviceId(type=hue.DeviceType[device_id['type']],
                         label=device_id['label']))

    async def set_conf(self, device_id, conf):
        if not device_id:
            return await self._hue_conn.transport.set_conf(None, conf)
        return await self._hue_conn.transport.set_conf(
            hue.DeviceId(type=hue.DeviceType[device_id['type']],
                         label=device_id['label']),
            conf)