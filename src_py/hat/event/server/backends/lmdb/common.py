import typing

import lmdb

from hat.event.server.common import (Event)
from hat.event.server.common import *  # NOQA


ExtFlushCb = typing.Callable[[lmdb.Transaction], None]


class Conditions:

    def matches(self, event: Event) -> bool:
        pass
