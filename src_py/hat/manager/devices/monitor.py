from hat import aio
from hat import json
from hat import juggler
from hat import util

from hat.manager import common


default_conf = {'address': 'ws://127.0.0.1:23022/ws'}


class Device(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._async_group = aio.Group()
        self._change_cbs = util.CallbackRegistry()
        self._client = None
        self._address = conf['address']
        self._mid = 0
        self._local_components = []
        self._global_components = []
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

        if action == 'set_rank':
            return await self._act_set_rank(*args)

        raise ValueError('invalid action')

    async def _client_loop(self, client):

        def on_change():
            self._mid = json.get(client.remote_data, 'mid') or 0
            self._local_components = \
                json.get(client.remote_data, 'local_components') or []
            self._global_components = \
                json.get(client.remote_data, 'global_components') or []
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

    async def _act_set_rank(self, cid, rank):
        if not self._client or not self._client.is_open:
            self._logger.log('set rank failed - not connected')
            return

        await self._client.send({'type': 'set_rank',
                                 'payload': {'cid': cid,
                                             'rank': rank}})
        self._logger.log(f'send set rank (cid: {cid}; rank: {rank})')

    def _update_data(self):
        self._data = {'address': self._address,
                      'mid': self._mid,
                      'local_components': self._local_components,
                      'global_components': self._global_components}
        self._change_cbs.notify(self._data)
