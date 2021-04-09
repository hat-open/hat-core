from hat.manager import common


default_master_conf = {}

default_slave_conf = {}


class Master(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._data = common.DataStorage()

    @property
    def data(self):
        return self._data

    def get_conf(self):
        return {}

    async def create(self):
        pass

    async def execute(self, action, *args):
        pass


class Slave(common.Device):

    def __init__(self, conf, logger):
        self._logger = logger
        self._data = common.DataStorage()

    @property
    def data(self):
        return self._data

    def get_conf(self):
        return {}

    async def create(self):
        pass

    async def execute(self, action, *args):
        pass
