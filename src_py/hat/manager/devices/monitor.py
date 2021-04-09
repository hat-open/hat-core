from hat import json
from hat import juggler
from hat.manager import common


default_conf = {'address': 'ws://127.0.0.1:23022/ws'}


class Device(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._client = None
        self._data = common.DataStorage({'address': conf['address'],
                                         'mid': 0,
                                         'local_components': [],
                                         'global_components': []})

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

        if action == 'set_rank':
            return await self._act_set_rank(*args)

        raise ValueError('invalid action')

    async def _client_loop(self, client):

        def on_change():
            mid = json.get(client.remote_data, 'mid')
            local_components = json.get(client.remote_data,
                                        'local_components')
            global_components = json.get(client.remote_data,
                                         'global_components')
            self._data.set([], dict(self._data.data,
                                    mid=mid or 0,
                                    local_components=local_components or [],
                                    global_components=global_components or []))

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

    async def _act_set_rank(self, cid, rank):
        if not self._client or not self._client.is_open:
            self._logger.log('set rank failed - not connected')
            return

        await self._client.send({'type': 'set_rank',
                                 'payload': {'cid': cid,
                                             'rank': rank}})
        self._logger.log(f'send set rank (cid: {cid}; rank: {rank})')
