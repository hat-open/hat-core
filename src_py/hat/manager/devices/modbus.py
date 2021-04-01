from hat import aio
from hat import util

from hat.manager import common


default_master_conf = {}

default_slave_conf = {}


class Master(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._async_group = aio.Group()
        self._change_cbs = util.CallbackRegistry()
        self._data = {}

    @property
    def async_group(self):
        return self._async_group

    @property
    def data(self):
        return self._data

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    def get_conf(self):
        return {}

    async def create(self):
        pass

    async def execute(self, action, *args):
        pass


class Slave(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._async_group = aio.Group()
        self._change_cbs = util.CallbackRegistry()
        self._data = {}

    @property
    def async_group(self):
        return self._async_group

    @property
    def data(self):
        return self._data

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    def get_conf(self):
        return {}

    async def create(self):
        pass

    async def execute(self, action, *args):
        pass
