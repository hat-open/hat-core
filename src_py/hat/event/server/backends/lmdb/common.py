import typing

import lmdb

from hat.event.server.common import Timestamp
from hat.event.server.common import *  # NOQA


ExtFlushCb = typing.Callable[[lmdb.Transaction, Timestamp], None]


class SystemData(typing.NamedTuple):
    server_id: int
    last_instance_id: typing.Optional[int]
    last_timestamp: typing.Optional[Timestamp]
