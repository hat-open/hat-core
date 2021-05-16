"""Orchestrator's controlled component"""

import asyncio
import contextlib
import datetime
import enum
import logging
import typing

from hat import aio
from hat import json
from hat import util
import hat.orchestrator.process


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


Status = enum.Enum('Status', [
    'STOPPED',
    'DELAYED',
    'STARTING',
    'RUNNING',
    'STOPPING'])


class Component(aio.Resource):
    """Component

    Args:
        conf: configuration defined by
            ``hat://orchestrator.yaml#/definitions/component``
        win32_job: win32 job instance

    """

    def __init__(self,
                 conf: json.Data,
                 win32_job: typing.Optional[hat.orchestrator.process.Win32Job] = None):  # NOQA
        self._conf = conf
        self._win32_job = win32_job
        self._status = Status.DELAYED if conf['delay'] else Status.STOPPED
        self._revive = conf['revive']
        self._change_cbs = util.CallbackRegistry(
            exception_cb=lambda e: mlog.warning(
                "change callback exception: %s", e, exc_info=e))
        self._started_queue = aio.Queue()
        self._async_group = aio.Group()
        self._async_group.spawn(self._run_loop)

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def status(self) -> Status:
        """Current status"""
        return self._status

    @property
    def name(self) -> str:
        """Component name"""
        return self._conf['name']

    @property
    def delay(self) -> float:
        """Delay in seconds"""
        return self._conf['delay']

    @property
    def revive(self) -> bool:
        """Revive component"""
        return self._revive

    def register_change_cb(self,
                           cb: typing.Callable[[], None]
                           ) -> util.RegisterCallbackHandle:
        """Register change callback

        All changes to revive and/or status properties (even those occuring
        due to call of async_close) are notified by calling registered
        callback.

        """
        return self._change_cbs.register(cb)

    def set_revive(self, revive: bool):
        """Set revive flag"""
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
                    started = await aio.wait_for(
                        self._started_queue.get_until_empty(), self.delay)
            self._started_queue.put_nowait(started)

            while True:
                await asyncio.sleep(self._conf['start_delay'])

                started = False
                while not (started or self.revive):
                    started = await self._started_queue.get_until_empty()
                    if not started:
                        self._set_status(Status.STOPPED)

                try:
                    self._set_status(Status.STARTING)
                    process = await aio.wait_for(self._start_process(),
                                                 self._conf['create_timeout'])
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    mlog.warning("error starting component %s: %s",
                                 self.name, e, exc_info=e)
                    self._set_status(Status.STOPPED)
                    continue

                try:
                    self._set_status(Status.RUNNING)
                    started = True

                    closing_future = self._async_group.spawn(
                        aio.call_on_done,
                        self._async_group.spawn(self._read_stdout, process),
                        process.wait_closing)

                    while started:
                        started_future = self._async_group.spawn(
                            self._started_queue.get_until_empty)
                        await asyncio.wait([started_future, closing_future],
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
        process = await hat.orchestrator.process.create_process(
            args=self._conf['args'],
            sigint_timeout=self._conf['sigint_timeout'],
            sigkill_timeout=self._conf['sigkill_timeout'])
        if self._win32_job:
            self._win32_job.add_process(process)
        mlog.info("component %s (%s) started", self.name, process.pid)
        return process

    async def _stop_process(self, process):
        await process.async_close()
        if process.returncode is None:
            mlog.info("component %s (%s) failed to stop",
                      self.name, process.pid)
        else:
            mlog.info("component %s (%s) stopped with return code %s",
                      self.name, process.pid, process.returncode)

    async def _read_stdout(self, process):
        try:
            while True:
                line = await process.readline()
                mlog.info("component %s (%s) stdout: %s",
                          self.name, process.pid, line)
                now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{now} {self.name} ({process.pid})] {line}")

        except ConnectionError:
            mlog.debug("component %s (%s) stdout closed",
                       self.name, process.pid)
