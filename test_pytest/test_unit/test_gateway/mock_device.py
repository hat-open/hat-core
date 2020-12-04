from hat import aio
from hat.gateway import common


device_type = 'mock'


async def create(conf, client, event_type_prefix):
    device = MockDevice()
    device._async_group = aio.Group()
    device._client = client
    device._event_type_prefix = event_type_prefix
    return device


class MockDevice(common.Device):

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self):
        await self._async_group.async_close()

    @property
    def client(self):
        return self._client

    @property
    def event_type_prefix(self):
        return self._event_type_prefix
