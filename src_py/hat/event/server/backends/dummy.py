"""Dummy backend

Simple backend which returns constat values. While backend is not closed,
all methods are successful and:

    * `DummyBackend.get_last_event_id` returns instance ``0``
    * `DummyBackend.register` returns input arguments
    * `DummyBackend.query` returns ``[]``

"""

import typing

from hat import aio
from hat import json
from hat.event.server import common


json_schema_id = None
json_schema_repo = None


async def create(conf: json.Data) -> 'DummyBackend':
    backend = DummyBackend()
    backend._async_group = aio.Group()
    return backend


class DummyBackend(common.Backend):

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    async def get_last_event_id(self,
                                server_id: int
                                ) -> common.EventId:
        result = common.EventId(server_id, 0)
        return await self._async_group.spawn(aio.call, lambda: result)

    async def register(self,
                       events: typing.List[common.Event]
                       ) -> typing.List[typing.Optional[common.Event]]:
        result = events
        return await self._async_group.spawn(aio.call, lambda: result)

    async def query(self,
                    data: common.QueryData
                    ) -> typing.List[common.Event]:
        result = []
        return await self._async_group.spawn(aio.call, lambda: result)
