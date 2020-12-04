from hat import aio
from hat import util


def create_backend(msgid):
    backend = MockBackend()
    backend._msgid = msgid
    backend._first_id = 0
    backend._last_id = 0
    backend._async_group = aio.Group()
    backend._change_cbs = util.CallbackRegistry()
    backend._msg_queue = aio.Queue()
    return backend


class MockBackend:

    @property
    def first_id(self):
        return self._first_id

    @property
    def last_id(self):
        return self._last_id

    def register_change_cb(self, cb):
        return self._change_cbs.register(cb)

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self):
        await self._async_group.async_close()

    async def register(self, timestamp, msg):
        if (not msg.msgid.startswith('test_syslog') and
                msg.msgid != 'hat.syslog.handler'):
            return
        await self._msg_queue.put((timestamp, msg))

    async def query(self, filter):
        pass
