Hat Core - Python Qt utility library
====================================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-qt` documentation - `<https://core.hat-open.com/docs/libraries/qt.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Parallel execution of Qt and asyncio threads::

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
