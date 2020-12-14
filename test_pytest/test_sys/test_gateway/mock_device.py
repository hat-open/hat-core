from hat import aio
from hat.gateway import common
import asyncio
import urllib.parse

import hat.event.common

device_type = 'mock'
json_schema_id = None
json_schema_repo = None


async def create(conf, client, event_type_prefix):

    device = MockDevice()
    device._async_group = aio.Group()
    device._client = client
    device._event_type_prefix = event_type_prefix
    device._name = conf['name']
    url = urllib.parse.urlparse(conf['address'])
    srv = await asyncio.start_server(
        lambda r, w: None, url.hostname, url.port)

    async def close_server():
        srv.close()
        await srv.wait_closed()

    device._async_group.spawn(device._receive_loop)
    device._async_group.spawn(aio.call_on_cancel, close_server)
    return device


class MockDevice(common.Device):

    @property
    def async_group(self):
        return self._async_group

    @property
    def client(self):
        return self._client

    @property
    def event_type_prefix(self):
        return self._event_type_prefix

    async def _receive_loop(self):
        try:
            while True:
                events = await self._client.receive()
                for e in events:
                    if e.event_type[-1] == 'seen':
                        continue
                    self._client.register([hat.event.common.RegisterEvent(
                        event_type=e.event_type + ['seen'],
                        source_timestamp=None,
                        payload=e.payload)])
        finally:
            pass
