import typing

import lmdb

from hat import aio
from hat.event.server.backends.lmdb import common


async def create(executor: aio.Executor,
                 env: lmdb.Environment,
                 name: str,
                 subscription: common.Subscription,
                 conditions: common.Condition
                 ) -> 'OrderedDb':
    pass


class OrderedDb:

    @property
    def has_changed(self) -> bool:
        return bool(self._changes)

    @property
    def subscription(self) -> common.Subscription:
        return self._subscription

    def add(self, events: typing.Iterable[common.Event]):
        pass

    async def query(self,
                    event_types: typing.Optional[typing.List[common.EventType]]
                    ) -> typing.Iterable[common.Event]:
        pass

    def create_ext_flush(self) -> common.ExtFlushCb:
        pass
