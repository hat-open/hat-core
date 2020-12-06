from pathlib import Path
import asyncio
import contextlib

from hat import aio
from hat import chatter
from hat import json
from hat import sbs
import hat.event.server.common


package_path = Path(__file__).parent

json_schema_id = "test://modules/remote.yaml#"
json_schema_repo = json.SchemaRepository(package_path / 'remote.yaml')

sbs_repo = sbs.Repository(chatter.sbs_repo, package_path / 'remote.sbs')


async def create(conf, engine):
    module = RemoteModule()
    module._subscriptions = conf['subscriptions']
    module._async_group = aio.Group()
    module._conn = await chatter.connect(sbs_repo, conf['address'])
    module._async_group.spawn(aio.call_on_cancel,
                              module._conn.async_close)
    module._send('ModuleCreate', None)
    return module


class RemoteModule(hat.event.server.common.Module):

    @property
    def subscriptions(self):
        return self._subscriptions

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self):
        self._send('ModuleClose', None)
        await self._async_group.async_close()

    async def create_session(self):
        self._send('SessionCreate', None)
        session = RemoteModuleSession()
        session._module = self
        session._async_group = self._async_group.create_subgroup()
        return session

    def _send(self, msg_type, msg):
        self._conn.send(chatter.Data('TestRemoteModule', msg_type, msg))


class RemoteModuleSession(hat.event.server.common.ModuleSession):

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self, events):
        self._module._send('SessionClose', None)
        await self._async_group.async_close()

    async def process(self, changes):
        self._module._send('Process', None)
        await asyncio.sleep(0)
        return hat.event.server.common.SessionChanges([], [])


async def create_server(address):

    def connection_cb(conn):
        server._async_group.spawn(_connection_read_loop, conn, server._queue)

    server = Server()
    server._queue = aio.Queue()
    server._async_group = aio.Group()

    srv = await chatter.listen(sbs_repo, address, connection_cb)
    server._async_group.spawn(aio.call_on_cancel, srv.async_close)
    return server


class Server:

    @property
    def queue(self):
        return self._queue

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self):
        await self._async_group.async_close()


async def _connection_read_loop(conn, queue):
    with contextlib.suppress(Exception):
        while True:
            msg = await conn.receive()
            queue.put_nowait(msg.data.type)
