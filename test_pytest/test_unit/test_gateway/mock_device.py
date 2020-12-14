from hat import aio
from hat.gateway import common


device_type = 'mock'
json_schema_id = None
json_schema_repo = None


async def create(conf, client, event_type_prefix):
    device = MockDevice()
    device._async_group = aio.Group()
    device._client = client
    device._event_type_prefix = event_type_prefix
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
