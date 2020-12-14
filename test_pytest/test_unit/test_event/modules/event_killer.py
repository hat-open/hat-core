from hat import aio
import hat.event.server
import hat.event.common


json_schema_id = None
json_schema_repo = None


async def create(conf, engine):
    module = ModuleEventKiller()
    module._async_group = aio.Group()
    module._engine = engine
    module._source = hat.event.server.common.Source(
        type=hat.event.server.common.SourceType.MODULE,
        name='EventKiller',
        id=4)
    module.session_queue = aio.Queue()
    return module


class ModuleEventKiller(hat.event.server.common.Module):

    @property
    def subscriptions(self):
        return [['*']]

    @property
    def async_group(self):
        return self._async_group

    async def create_session(self):
        session = ModuleEventKillerSession()
        session._async_group = aio.Group()
        session._module = self
        session.changes_notified_new = []
        session.changes_notified_deleted = []
        session.changes_result_new = []
        session.changes_result_deleted = []
        self.session_queue.put_nowait(session)
        return session


class ModuleEventKillerSession(hat.event.server.common.ModuleSession):

    @property
    def async_group(self):
        return self._async_group

    async def process(self, changes):
        self.changes_notified_new += changes.new
        self.changes_notified_deleted += changes.deleted
        changes_res = hat.event.server.common.SessionChanges(
            new=[],
            deleted=changes.new)
        self.changes_result_new += changes_res.new
        self.changes_result_deleted += changes_res.deleted
        return changes_res
