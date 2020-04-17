import asyncio
import contextlib
import datetime
import enum
import logging
import signal
import subprocess
import sys

from hat import util
from hat.util import aio


mlog = logging.getLogger(__name__)

start_delay = 0.5
"""float: process start delay in seconds"""

create_timeout = 2
"""float: create process timeout in seconds"""

sigint_timeout = 5
"""float: SIGINT timeout in seconds"""

sigkill_timeout = 2
"""float: SIGKILL timeout in seconds"""


Status = util.extend_enum_doc(enum.Enum('Status', [
    'STOPPED',
    'DELAYED',
    'STARTING',
    'RUNNING',
    'STOPPING']))


class Component:
    """Component

    Args:
        conf (hat.json.Data): configuration defined by
            ``hat://orchestrator.yaml#/definitions/component``

    """

    def __init__(self, conf):
        self._conf = conf
        self._status = Status.DELAYED if conf['delay'] else Status.STOPPED
        self._revive = conf['revive']
        self._change_cbs = util.CallbackRegistry(
            exception_cb=lambda e: mlog.warning(
                "change callback exception: %s", e, exc_info=e))
        self._started_queue = aio.Queue()
        self._async_group = aio.Group()
        self._async_group.spawn(self._run_loop)

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    @property
    def status(self):
        """Status: current status"""
        return self._status

    @property
    def name(self):
        """str: component name"""
        return self._conf['name']

    @property
    def args(self):
        """List[str]: command line arguments"""
        return self._conf['args']

    @property
    def delay(self):
        """float: delay in seconds"""
        return self._conf['delay']

    @property
    def revive(self):
        """bool: revive component"""
        return self._revive

    def register_change_cb(self, cb):
        """Register change callback

        All changes to revive and/or status properties (even those occuring
        due to call of async_close) are notified by calling registered
        callback.

        Args:
            cb (Callable[[],None]): change callback

        Returns:
            util.RegisterCallbackHandle

        """
        return self._change_cbs.register(cb)

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    def set_revive(self, revive):
        """Set revive flag

        Args:
            revive (bool): revive flag

        """
        if revive == self.revive:
            return
        self._revive = revive
        if revive and self._status != Status.DELAYED:
            self.start()
        self._change_cbs.notify()

    def start(self):
        """Start component"""
        self._started_queue.put_nowait(True)

    def stop(self):
        """Stop component"""
        self._started_queue.put_nowait(False)

    async def _run_loop(self):
        process = None

        try:
            started = True
            if self.delay:
                with contextlib.suppress(asyncio.TimeoutError):
                    started = await asyncio.wait_for(
                        self._started_queue.get_until_empty(), self.delay)
            self._started_queue.put_nowait(started)

            while True:
                await asyncio.sleep(start_delay)

                started = False
                while not (started or self.revive):
                    started = await self._started_queue.get_until_empty()
                    if not started:
                        self._set_status(Status.STOPPED)

                try:
                    self._set_status(Status.STARTING)
                    process = await asyncio.wait_for(self._start_process(),
                                                     create_timeout)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    mlog.warning("error starting component %s: %s",
                                 self.name, e, exc_info=e)
                    self._set_status(Status.STOPPED)
                    continue

                try:
                    self._set_status(Status.RUNNING)
                    read_future = self._async_group.spawn(self._read_stdout,
                                                          process)
                    started = True
                    while started:
                        started_future = self._async_group.spawn(
                            self._started_queue.get_until_empty)
                        await asyncio.wait([started_future, read_future],
                                           return_when=asyncio.FIRST_COMPLETED)
                        if started_future.done():
                            started = started_future.result()
                        else:
                            started_future.cancel()
                            break
                finally:
                    self._set_status(Status.STOPPING)
                    await self._stop_process(process)
                    process = None
                    self._set_status(Status.STOPPED)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            mlog.error("component %s run loop error: %s",
                       self.name, e, exc_info=e)
        finally:
            if process:
                await aio.uncancellable(self._stop_process(process),
                                        raise_cancel=False)
            self._set_status(Status.STOPPED)
            self._async_group.close()

    def _set_status(self, status):
        if status == self.status:
            return
        mlog.debug("component %s status change: %s -> %s",
                   self.name, self.status, status)
        self._status = status
        self._change_cbs.notify()

    async def _start_process(self):
        creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP
                         if sys.platform == 'win32' else 0)
        process = await asyncio.create_subprocess_exec(
            *self.args, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, creationflags=creationflags)
        mlog.info("component %s (%s) started", self.name, process.pid)
        return process

    async def _stop_process(self, process):
        if process.returncode is None:
            with contextlib.suppress(Exception):
                process.send_signal(signal.CTRL_BREAK_EVENT
                                    if sys.platform == 'win32'
                                    else signal.SIGINT)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), sigint_timeout)
        if process.returncode is None:
            with contextlib.suppress(Exception):
                process.kill()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), sigkill_timeout)
        if process.returncode is None:
            mlog.info("component %s (%s) failed to stop",
                      self.name, process.pid)
        else:
            mlog.info("component %s (%s) stopped with return code %s",
                      self.name, process.pid, process.returncode)

    async def _read_stdout(self, process):
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            line = line.decode('utf-8', 'ignore').rstrip()
            mlog.info("component %s (%s) stdout: %s",
                      self.name, process.pid, line)
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{now} {self.name} ({process.pid})] {line}")
