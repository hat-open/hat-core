from hat import json
from hat import juggler
from hat.manager import common


default_conf = {'address': 'ws://127.0.0.1:23021/ws'}


class Device(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._client = None
        self._data = common.DataStorage({'address': conf['address'],
                                         'components': []})

    @property
    def data(self):
        return self._data

    def get_conf(self):
        return {'address': self._data.data['address']}

    async def create(self):
        address = self._data.data['address']
        self._client = await juggler.connect(address)
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
            components = json.get(client.remote_data, 'components') or []
            self._data.set('components', components)

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
        self._data.set('address', address)

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
