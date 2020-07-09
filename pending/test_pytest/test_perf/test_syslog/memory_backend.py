from hat.util import aio
from hat import util
import hat.syslog.server.common


async def create_backend(_):
    backend = MemoryBackend()
    backend._first_id = None
    backend._last_id = None
    backend._entries = []
    backend._async_group = aio.Group(lambda e: print(f"memory: error in {e}"))
    backend._change_cbs = util.CallbackRegistry()
    return backend


class MemoryBackend:

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
        if self._last_id is None:
            self._last_id = 0
            self._first_id = 1
        self._last_id += 1
        entry = hat.syslog.server.common.Entry(
            id=self._last_id,
            timestamp=timestamp,
            msg=msg)
        self._entries.append(entry)
        self._change_cbs.notify([entry])

    async def query(self, filter):

        def _get_filter(query_opt):
            return {
                'max_results': _max_results,
                'last_id': _last_id,
                'entry_timestamp_from': _entry_timestamp_from,
                'entry_timestamp_to': _entry_timestamp_to,
                'facility': _facility,
                'severity': _severity,
                'hostname': _hostname,
                'app_name': _app_name,
                'procid': _procid,
                'msgid': _msgid,
                'msg': _msg}[query_opt]

        ret = self._entries
        for f_name, f_value in filter._asdict().items():
            if f_value is None:
                continue
            ret = _get_filter(f_name)(ret, f_value)
        return ret


def _max_results(entries, max_results):
    return entries[:max_results]


def _last_id(entries, val):
    return filter(lambda i: i.id <= val, entries)


def _entry_timestamp_from(entries, val):
    return filter(lambda i: i.timestamp >= val, entries)


def _entry_timestamp_to(entries, val):
    return filter(lambda i: i.timestamp >= val, entries)


def _facility(entries, val):
    return filter(lambda i: i.msg.facility == val, entries)


def _severity(entries, val):
    return filter(lambda i: i.msg.severity == val, entries)


def _hostname(entries, val):
    return filter(lambda i: i.msg.hostname == val, entries)


def _app_name(entries, val):
    return filter(lambda i: i.msg.hostname == val, entries)


def _procid(entries, val):
    return filter(lambda i: i.msg.procid == val, entries)


def _msgid(entries, val):
    return filter(lambda i: i.msg.msgid == val, entries)


def _msg(entries, val):
    return filter(lambda i: i.msg.msg == val, entries)
