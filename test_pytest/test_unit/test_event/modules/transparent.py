from hat.util import aio
import hat.event.server
import hat.event.common


async def create(conf, engine):
    module = ModuleTransparent()
    module._async_group = aio.Group()
    module._engine = engine
    module._source = hat.event.server.common.Source(
        type=hat.event.server.common.SourceType.MODULE,
        name='ModuleTransparent',
        id=3)
    module.session_queue = aio.Queue()
    return module


class ModuleTransparent(hat.event.server.common.Module):

    @property
    def subscriptions(self):
        return [['*']]

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self):
        await self._async_group.async_close()

    async def create_session(self):
        session = ModuleTransparentSession()
        session._async_group = aio.Group()
        session._module = self
        session.changes_notified_new = []
        session.changes_notified_deleted = []
        session.changes_result_new = []
        session.changes_result_deleted = []
        session.events_on_close = None
        self.session_queue.put_nowait(session)
        return session


class ModuleTransparentSession(hat.event.server.common.ModuleSession):

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self, events):
        self.events_on_close = events
        await self._async_group.async_close()

    async def process(self, changes):
        self.changes_notified_new += changes.new
        self.changes_notified_deleted += changes.deleted
        changes_res = hat.event.server.common.SessionChanges(new=[],
                                                             deleted=[])
        self.changes_result_new += changes_res.new
        self.changes_result_deleted += changes_res.deleted
        return changes_res
