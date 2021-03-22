import time
import typing

from hat import json
from hat import util


log_size = 100


class Log:

    def __init__(self):
        self._data = []
        self._change_cbs = util.CallbackRegistry()

    @property
    def data(self) -> json.Data:
        return self._data

    def register_change_cb(self,
                           cb: typing.Callable[[json.Data], None]
                           ) -> util.RegisterCallbackHandle:
        return self._change_cbs.register(cb)

    def log(self, msg: str):
        self._data = [{'timestamp': time.time(),
                       'message': msg},
                      *self._data][:log_size]
        self._change_cbs.notify(self._data)
