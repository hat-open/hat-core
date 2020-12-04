"""Parallel execution of Qt and asyncio threads"""

import concurrent.futures
import queue
import sys
import threading
import asyncio
import functools
import typing

import PySide2.QtCore
import PySide2.QtWebEngineWidgets
import PySide2.QtWidgets

from hat import aio


QtExecutor = typing.Callable[..., typing.Awaitable[typing.Any]]
"""First argument is Callable called with additional arguments"""

AsyncMain = typing.Callable[..., typing.Awaitable[typing.Any]]
"""First argument is QtExecutor"""


def run(async_main: AsyncMain, *args, **kwargs):
    """Run Qt application with additional asyncio thread

    Args:
        async_main: asyncio main entry point
        args: aditional positional arguments passed to `async_main`
        kwargs: aditional keyword arguments passed to `async_main`

    """
    app = PySide2.QtWidgets.QApplication(sys.argv)
    executor = _QtExecutor()
    async_thread = threading.Thread(target=_run_async_thread,
                                    args=(app, executor, async_main,
                                          args, kwargs),
                                    daemon=True)
    async_thread.start()
    return app.exec_()


class _QtExecutor(PySide2.QtCore.QObject, concurrent.futures.Executor):

    def __init__(self):
        super().__init__()
        self.__closed = False
        self.__queue = queue.Queue()

    def submit(self, fn, /, *args, **kwargs):
        if self.__closed:
            raise RuntimeError()
        f = concurrent.futures.Future()
        self.__queue.put_nowait((f, fn, args, kwargs))
        PySide2.QtCore.QMetaObject.invokeMethod(
            self, "_ext_qt_execute", PySide2.QtCore.Qt.QueuedConnection)
        return f

    def shutdown(self, wait=True):
        self.__closed = True

    @PySide2.QtCore.Slot()
    def _ext_qt_execute(self):
        f, fn, args, kwargs = self.__queue.get()
        try:
            f.set_result(fn(*args, **kwargs))
        except Exception as e:
            f.set_exception(e)


def _run_async_thread(app, executor, async_main, args, kwargs):
    aio.init_asyncio()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        qt_executor = functools.partial(loop.run_in_executor, executor)
        loop.run_until_complete(async_main(qt_executor, *args, **kwargs))
    finally:
        executor.submit(app.exit)
