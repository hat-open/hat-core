import hat.monitor.server.master

from hat import aio
from hat import util


def create_master(mid=0, components=[]):
    master = MockMaster()
    master._async_group = aio.Group()
    master._mid = mid
    master._components = components
    master._components_queue = aio.Queue()
    master._rank_queue = aio.Queue()
    master._change_cbs = util.CallbackRegistry()
    return master


class MockMaster(hat.monitor.server.master.Master):

    @property
    def closed(self):
        return self._async_group.closed

    @property
    def mid(self):
        return self._mid

    @property
    def components(self):
        return self._components

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    async def async_close(self):
        await self._async_group.async_close()

    def set_components(self, components):
        self._components_queue.put_nowait(components)

    def set_rank(self, cid, mid, rank):
        self._rank_queue.put_nowait((cid, mid, rank))

    def _set_mid(self, mid):
        self._components = [i._replace(mid=mid) if i.mid == self._mid else i
                            for i in self._components]
        self._mid = mid
        self._change_cbs.notify()

    def _set_components(self, components):
        self._components = components
        self._change_cbs.notify()
