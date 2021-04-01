from hat import aio
from hat import json
from hat import juggler
from hat import util

from hat.manager import common


default_conf = {'address': 'ws://127.0.0.1:23021/ws'}


class Device(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._async_group = aio.Group()
        self._change_cbs = util.CallbackRegistry()
        self._client = None
        self._address = conf['address']
        self._components = []
        self._data = None
        self._update_data()

    @property
    def async_group(self):
        return self._async_group

    @property
    def data(self):
        return self._data

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    def get_conf(self):
        return {'address': self._address}

    async def create(self):
        self._client = await juggler.connect(self._address)
        self._client.async_group.spawn(self._client_loop, self._client)
        return self._client

    async def execute(self, action, *args):
        if action == 'set_address':
            return self._act_set_address(*args)

        if action == 'start':
            return await self._act_start(*args)

        if action == 'stop':
            return await self._act_stop(*args)

        if action == 'set_revive':
            return await self._act_set_revive(*args)

        raise ValueError('invalid action')

    async def _client_loop(self, client):

        def on_change():
            self._components = json.get(client.remote_data, 'components') or []
            self._update_data()

        try:
            with client.register_change_cb(on_change):
                on_change()
                await client.wait_closing()

        except ConnectionError:
            pass

        finally:
            client.close()

    def _act_set_address(self, address):
        self._logger.log(f'changing address to {address}')
        self._address = address
        self._update_data()

    async def _act_start(self, component_id):
        if not self._client or not self._client.is_open:
            self._logger.log('start failed - not connected')
            return

        await self._client.send({'type': 'start',
                                 'payload': {'id': component_id}})
        self._logger.log('send start')

    async def _act_stop(self, component_id):
        if not self._client or not self._client.is_open:
            self._logger.log('stop failed - not connected')
            return

        await self._client.send({'type': 'stop',
                                 'payload': {'id': component_id}})
        self._logger.log('send stop')

    async def _act_set_revive(self, component_id, revive):
        if not self._client or not self._client.is_open:
            self._logger.log('set revive failed - not connected')
            return

        await self._client.send({'type': 'revive',
                                 'payload': {'id': component_id,
                                             'value': revive}})
        self._logger.log(f'send revive {revive}')

    def _update_data(self):
        self._data = {'address': self._address,
                      'components': self._components}
        self._change_cbs.notify(self._data)
