"""Backend implementation

Attributes:
    mlog (logging.Logger): module logger
    register_delay (float): registration delay in seconds
    register_queue_size (int): registration queue size
    register_queue_treshold (int): registration queue threshold

"""

import asyncio
import contextlib
import logging

from hat import aio
from hat import util
from hat.syslog.server import common
from hat.syslog.server import database


mlog = logging.getLogger(__name__)


register_delay = 0.1
register_queue_size = 50
register_queue_treshold = 10


async def create_backend(conf):
    """Create backend

    Args:
        conf (hat.syslog.server.conf.BackendConf): configuration

    Returns:
        Backend

    """

    db = await database.create_database(conf.path, conf.disable_journal)
    try:
        first_id = await db.get_first_id()
        last_id = await db.get_last_id()
    except BaseException:
        await aio.uncancellable(db.async_close())
        raise

    backend = Backend()
    backend._conf = conf
    backend._db = db
    backend._first_id = first_id
    backend._last_id = last_id
    backend._async_group = aio.Group()
    backend._change_cbs = util.CallbackRegistry()
    backend._msg_queue = aio.Queue(register_queue_size)
    backend._executor = aio.create_executor()

    backend._async_group.spawn(aio.call_on_cancel, db.async_close)
    backend._async_group.spawn(backend._loop)

    mlog.debug('created backend with database %s', conf.path)
    return backend


class Backend:

    @property
    def first_id(self):
        """Optional[int]: first entry id"""
        return self._first_id

    @property
    def last_id(self):
        """Optional[int]: last entry id"""
        return self._last_id

    def register_change_cb(self, cb):
        """Register change callback

        Callback is called if `first_id` changes and/or `lats_id` changes
        and/or new entries are available (passed as argument to registered
        callback).

        Args:
            cb (Callable[[List[common.Entry]],None]): callback

        Returns:
            util.RegisterCallbackHandle

        """
        return self._change_cbs.register(cb)

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    async def register(self, timestamp, msg):
        """Register message

        Registration adds msg to registration queue. If queue is full, wait
        until message can be successfully added.

        When message is added to empty queue, registration delay timer is
        started. Once delay timer expires or if number of messages in queue
        is greater than threshold, all messages are removed from queue and
        inserted into sqlite database.

        Args:
            timestamp (float): timestamp
            msg (common.Msg): message

        """
        await self._msg_queue.put((timestamp, msg))

    async def query(self, filter):
        """Query entries

        Args:
            filter (common.Filter): filter

        Returns:
            List[common.Entry]

        """
        return await self._db.query(filter)

    async def _loop(self):
        try:
            while True:
                msgs = await self._get_msgs()
                await self._process_msgs(msgs)
        except Exception as e:
            mlog.warn("backend loop error: %s", e, exc_info=e)
        finally:
            self._msg_queue.close()
            self._async_group.close()
            mlog.debug('backend loop closed')

    async def _get_msgs(self):
        loop = asyncio.get_running_loop()
        msgs = []

        msg = await self._msg_queue.get()
        msgs.append(msg)

        start = loop.time()
        while True:
            while not self._msg_queue.empty():
                msgs.append(self._msg_queue.get_nowait())
            timeout = register_delay - (loop.time() - start)
            if timeout <= 0:
                break
            if len(msgs) >= register_queue_treshold:
                break
            async_group = aio.Group()
            try:
                f = async_group.spawn(self._msg_queue.get)
                await asyncio.wait_for(asyncio.shield(f), timeout)
            except asyncio.TimeoutError:
                break
            finally:
                await aio.uncancellable(async_group.async_close())
                if not f.cancelled():
                    msgs.append(f.result())

        while not self._msg_queue.empty():
            msgs.append(self._msg_queue.get_nowait())
        return msgs

    async def _process_msgs(self, msgs):
        mlog.debug("registering new messages (message count: %s)...",
                   len(msgs))
        entries = await self._db.add_msgs(msgs)
        if not entries:
            return

        self._last_id = entries[0].id
        if self._first_id is None:
            self._first_id = entries[-1].id

        mlog.debug("backend state changed (first_id: %s; last_id: %s)",
                   self._first_id, self._last_id)
        self._change_cbs.notify(entries)

        if self._conf.high_size <= 0:
            return
        if self._last_id - self._first_id + 1 <= self._conf.high_size:
            return

        mlog.debug("database cleanup starting...")
        await self._db_cleanup()

    async def _db_cleanup(self):
        first_id = self._last_id - self._conf.low_size + 1
        if first_id > self._last_id:
            first_id = None
        if first_id <= self._first_id:
            return

        if self._conf.enable_archive:
            mlog.debug("archiving database entries...")
            await self._archive_db(first_id)

        await self._db.delete(first_id)
        self._first_id = first_id
        if self._first_id is None:
            self._last_id = None

        mlog.debug("backend state changed (first_id: %s; last_id: %s)",
                   self._first_id, self._last_id)
        self._change_cbs.notify([])

    async def _archive_db(self, first_id):
        archive_path = await self._async_group.spawn(
            self._executor, _ext_get_new_archive_path, self._conf.path)
        archive = await database.create_database(
            archive_path, self._conf.disable_journal)
        try:
            entries = await self._db.query(common.Filter(
                last_id=first_id - 1 if first_id is not None else None))
            await archive.add_entries(entries)
        finally:
            await aio.uncancellable(archive.async_close())


def _ext_get_new_archive_path(db_path):
    counter = 1
    for i in db_path.parent.glob(db_path.name + '.*'):
        with contextlib.suppress(ValueError):
            index = int(i.name.split('.')[-1])
            if index > counter:
                counter = index
    return db_path.parent / f"{db_path.name}.{counter}"
