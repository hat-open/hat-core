from hat import aio
import hat.event.server
import hat.event.common


json_schema_id = None
json_schema_repo = None


async def create(conf, engine):
    module = CopierModule()
    module._async_group = aio.Group()
    module._engine = engine
    module._source = hat.event.server.common.Source(
        type=hat.event.server.common.SourceType.MODULE,
        name='CopierModule',
        id=1)
    return module


class CopierModule(hat.event.server.common.Module):

    @property
    def async_group(self):
        return self._async_group

    @property
    def subscriptions(self):
        return [['*']]

    async def create_session(self):
        session = CopierModuleSession()
        session._async_group = aio.Group()
        session._module = self
        return session


class CopierModuleSession(hat.event.server.common.ModuleSession):

    @property
    def async_group(self):
        return self._async_group

    async def process(self, changes):
        new = []
        for proc_event in changes.new:
            new_proc_event = self._module._engine.create_process_event(
                self._module._source,
                hat.event.common.RegisterEvent(
                    event_type=proc_event.event_type + ['copy'],
                    source_timestamp=hat.event.common.now(),
                    payload=proc_event.payload))
            new.append(new_proc_event)
        changes_res = hat.event.server.common.SessionChanges(new=new,
                                                             deleted=[])
        return changes_res
