import typing

import lmdb

from hat.event.server.common import (Event,
                                     Timestamp)
from hat.event.server.common import *  # NOQA


ExtFlushCb = typing.Callable[[lmdb.Transaction], None]


class SystemData(typing.NamedTuple):
    server_id: int
    last_instance_id: typing.Optional[int]
    last_timestamp: typing.Optional[Timestamp]


class Conditions:

    def matches(self, event: Event) -> bool:
        pass
