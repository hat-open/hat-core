.. _hat-qt:

`hat.qt` - Python Qt utility library
====================================

This library provides utility enhancements to
`PySide2 library <https://pypi.org/project/PySide2/>`_.


.. _hat-qt-run:

`hat.qt.run`
------------

`hat.qt.run` provides wrapper for running PySide2 application main event loop.
Prior to starting PySide event loop, new thread is started which runs
newly initialized asyncio loop. Purpose of asyncio loop is to execute
task created by calling provided `async_main` argument. Once PySide2 or asyncio
loop finishes, `run` will return PySide2 loop run result.

During execution of `async_main`, new executor is provided which enables
execution of code inside PySide2 loop initiated from asyncio loop.

::

    QtExecutor = typing.Callable[..., typing.Awaitable[typing.Any]]

    AsyncMain = typing.Callable[..., typing.Awaitable[typing.Any]]

    def run(async_main: AsyncMain, *args, **kwargs): ...

Example usage::

    async def async_main(executor):
        asyncio_tid = threading.get_ident()
        result = await executor(threading.get_ident)
        assert result == qt_tid
        assert asyncio_tid != qt_tid

    qt_tid = threading.get_ident()
    run(async_main)


API
---

API reference is available as part of generated documentation:

    * `Python hat.qt module <../pyhat/hat/qt.html>`_
