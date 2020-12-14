"""Dummy backend

Simple backend which returns constat values. While backend is not closed,
all methods are successful and:

    * :meth:`DummyBackend.get_event_type_id_mappings` returns ``{}``
    * :meth:`DummyBackend.get_event_type_id_mappings` returns
      ``common.EventId(server_id, 0)``
    * :meth:`DummyBackend.query` returns ``[]``

"""

from hat import aio
from hat.event.server import common


json_schema_id = None
json_schema_repo = None


async def create(conf):
    """Create DummyBackend

    Args:
        conf (hat.json.Data): configuration

    Returns:
        DummyBackend

    """
    backend = DummyBackend()
    backend._async_group = aio.Group()
    return backend


class DummyBackend(common.Backend):

    @property
    def async_group(self):
        return self._async_group

    async def async_close(self):
        """See :meth:`common.Backend.async_close`"""
        await self._async_group.async_close()

    async def get_last_event_id(self, server_id):
        """See :meth:`common.Backend.get_last_event_id`"""
        return await self._async_group.spawn(
            aio.call, lambda: common.EventId(server_id, 0))

    async def register(self, events):
        """See :meth:`common.Backend.register`"""
        return await self._async_group.spawn(aio.call, lambda: None)

    async def query(self, data):
        """See :meth:`common.Backend.query`"""
        return await self._async_group.spawn(aio.call, lambda: [])
