Hat Core - Python async utility library
=======================================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-aio` documentation - `<https://core.hat-open.com/docs/libraries/aio.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Async utility functions.

* `hat.aio.first`::

    async def first(xs: typing.AsyncIterable[T],
                    fn: typing.Callable[[T], bool] = lambda _: True,
                    default: typing.Optional[T] = None
                    ) -> typing.Optional[T]:
        """Return the first element from async iterable that satisfies
        predicate `fn`, or `default` if no such element exists.

        Args:
            xs: async collection
            fn: predicate
            default: default value

        Example::

            async def async_range(x):
                for i in range(x):
                    await asyncio.sleep(0)
                    yield i

            assert await first(async_range(3)) == 0
            assert await first(async_range(3), lambda x: x > 1) == 2
            assert await first(async_range(3), lambda x: x > 2) is None
            assert await first(async_range(3), lambda x: x > 2, 123) == 123

        """


* ``hat.aio.uncancellable``::

    async def uncancellable(f: asyncio.Future,
                            raise_cancel: bool = True
                            ) -> typing.Any:
        """Uncancellable execution of a Future.

        Future is shielded and its execution cannot be interrupted.

        If `raise_cancel` is `True` and the Future gets canceled,
        `asyncio.CancelledError` is reraised after the Future finishes.

        Warning:
            If `raise_cancel` is `False`, this method suppresses
            `asyncio.CancelledError` and stops its propagation. Use with
            caution.

        Args:
            f: future
            raise_cancel: raise CancelledError flag

        Returns:
            future's result

        """


* `hat.aio.call`, `hat.aio.call_on_cancel` and `hat.aio.call_on_done`::

    async def call(fn: AsyncCallable, *args, **kwargs) -> typing.Any:
        """Call a function or a coroutine (or other callable object).

        Call the `fn` with `args` and `kwargs`. If result of this call is
        awaitable, it is awaited and returned. Otherwise, result is immediately
        returned.

        Args:
            fn: callable object
            args: additional positional arguments
            kwargs: additional keyword arguments

        Returns:
            awaited result or result

        Example:

            def f1(x):
                return x

            def f2(x):
                f = asyncio.Future()
                f.set_result(x)
                return f

            async def f3(x):
                return x

            assert 'f1' == await hat.aio.call(f1, 'f1')
            assert 'f2' == await hat.aio.call(f2, 'f2')
            assert 'f3' == await hat.aio.call(f3, 'f3')

        """

    async def call_on_cancel(fn: AsyncCallable, *args, **kwargs) -> typing.Any:
        """Call a function or a coroutine when canceled.

        When canceled, `fn` is called with `args` and `kwargs` by using
        `call` coroutine.

        Args:
            fn: function or coroutine
            args: additional function arguments
            kwargs: additional function keyword arguments

        Returns:
            function result

        Example::

            f = asyncio.Future()
            group = Group()
            group.spawn(call_on_cancel, f.set_result, 123)
            assert not f.done()
            await group.async_close()
            assert f.result() == 123

        """

    async def call_on_done(f: typing.Awaitable,
                           fn: AsyncCallable,
                           *args, **kwargs
                           ) -> typing.Any:
        """Call a function or a coroutine when awaitable is done.

        When `f` is done, `fn` is called with `args` and `kwargs` by using
        `call` coroutine.

        If this coroutine is canceled before `f` is done, `f` is canceled and `fn`
        is not called.

        If this coroutine is canceled after `f` is done, `fn` call is canceled.

        Args:
            f: awaitable future
            fn: function or coroutine
            args: additional function arguments
            kwargs: additional function keyword arguments

        Returns:
            function result

        Example::

            f = asyncio.Future()
            group = Group()
            group.spawn(call_on_done, f, group.close)
            assert group.is_open
            f.set_result(None)
            await group.wait_closed()
            assert group.is_closed

        """


* `hat.aio.create_executor`::

    def create_executor(*args: typing.Any,
                        executor_cls: typing.Type = concurrent.futures.ThreadPoolExecutor,
                        loop: typing.Optional[asyncio.AbstractEventLoop] = None
                        ) -> typing.Callable[..., typing.Awaitable]:
        """Create `asyncio.loop.run_in_executor` wrapper.

        Returns a coroutine that takes a function and its arguments, executes the
        function using executor created from `executor_cls` and `args`; and
        returns the result.

        Args:
            args: executor args
            executor_cls: executor class
            loop: asyncio loop

        Returns:
            executor coroutine

        Example::

            executor1 = create_executor()
            executor2 = create_executor()
            tid1 = await executor1(threading.get_ident)
            tid2 = await executor2(threading.get_ident)
            assert tid1 != tid2

        """


* `hat.aio.init_asyncio` and `hat.aio.run_asyncio`::

    def init_asyncio(policy: typing.Optional[asyncio.AbstractEventLoopPolicy] = None):
        """Initialize asyncio.

        Sets event loop policy (if ``None``, instance of
        `asyncio.DefaultEventLoopPolicy` is used).

        After policy is set, new event loop is created and associated with current
        thread.

        On Windows, `asyncio.WindowsProactorEventLoopPolicy` is used as default
        policy.

        """

    def run_asyncio(future: typing.Awaitable, *,
                    handle_signals=True,
                    create_loop=False
                    ) -> typing.Any:
        """Run asyncio loop until the `future` is completed and return the result.

        If `handle_signals` is ``True``, SIGINT and SIGTERM handlers are
        temporarily overridden. Instead of raising ``KeyboardInterrupt`` on every
        signal reception, Future is canceled only once. Additional signals are
        ignored. On Windows, SIGBREAK (CTRL_BREAK_EVENT) handler is also
        overridden.

        If `create_loop` is set to ``True``, new event loop is created and set
        as thread's default event loop.

        On Windows, asyncio loop gets periodically woken up (every 0.5 seconds).

        Args:
            future: future or coroutine
            handle_signals: handle signals flag
            create_loop: create new event loop

        Returns:
            future's result

        Example::

            async def run():
                await asyncio.sleep(0)
                return 123

            result = run_asyncio(run())
            assert result == 123

        """


* `hat.aio.Queue`::

    class QueueClosedError(Exception):
        """Raised when trying to use a closed queue."""

    class QueueEmptyError(Exception):
        """Raised if queue is empty."""

    class QueueFullError(Exception):
        """Raised if queue is full."""

    class Queue:
        """Asyncio queue which implements AsyncIterable and can be closed.

        Interface and implementation are based on `asyncio.Queue`.

        If `maxsize` is less than or equal to zero, the queue size is infinite.

        Args:
            maxsize: maximum number of items in the queue

        Example::

            async def async_sum():
                result = 0
                async for i in queue:
                    result += i
                return result

            queue = Queue(maxsize=1)
            f = asyncio.ensure_future(async_sum())
            await queue.put(1)
            await queue.put(2)
            await queue.put(3)
            assert not f.done()
            queue.close()
            assert 6 == await f

        """

        def __init__(self, maxsize: int = 0): ...

        def __aiter__(self): ...

        async def __anext__(self): ...

        def __str__(self): ...

        def __len__(self): ...

        @property
        def maxsize(self) -> int:
            """Maximum number of items in the queue."""

        @property
        def is_closed(self) -> bool:
            """Is queue closed."""

        def empty(self) -> bool:
            """``True`` if queue is empty, ``False`` otherwise."""

        def full(self) -> bool:
            """``True`` if queue is full, ``False`` otherwise."""

        def qsize(self) -> int:
            """Number of items currently in the queue."""

        def close(self):
            """Close the queue."""

        def get_nowait(self) -> typing.Any:
            """Return an item if one is immediately available, else raise
            `QueueEmptyError`.

            Raises:
                QueueEmptyError

            """

        def put_nowait(self, item: typing.Any):
            """Put an item into the queue without blocking.

            If no free slot is immediately available, raise `QueueFullError`.

            Raises:
                QueueFullError

            """

        async def get(self) -> typing.Any:
            """Remove and return an item from the queue.

            If queue is empty, wait until an item is available.

            Raises:
                QueueClosedError

            """

        async def put(self, item: typing.Any):
            """Put an item into the queue.

            If the queue is full, wait until a free slot is available before adding
            the item.

            Raises:
                QueueClosedError

            """

        async def get_until_empty(self) -> typing.Any:
            """Empty the queue and return the last item.

            If queue is empty, wait until at least one item is available.

            Raises:
                QueueClosedError

            """

        def get_nowait_until_empty(self) -> typing.Any:
            """Empty the queue and return the last item if at least one
            item is immediately available, else raise `QueueEmptyError`.

            Raises:
                QueueEmptyError

            """


* `hat.aio.Group`::

    ExceptionCb = typing.Callable[[Exception], None]
    """Exception callback"""

    class Group:
        """Group of asyncio Tasks.

        Group enables creation and management of related asyncio Tasks. The
        Group ensures uninterrupted execution of Tasks and Task completion upon
        Group closing.

        Group can contain subgroups, which are independent Groups managed by the
        parent Group.

        If a Task raises exception, other Tasks continue to execute.

        If `exception_cb` handler is ``None``, exceptions are logged with level
        WARNING.

        """

        def __init__(self,
                     exception_cb: typing.Optional[ExceptionCb] = None,
                     *,
                     loop: typing.Optional[asyncio.AbstractEventLoop] = None): ...

        @property
        def is_open(self) -> bool:
            """``True`` if group is not closing or closed, ``False`` otherwise."""

        @property
        def is_closing(self) -> bool:
            """Is group closing or closed."""

        @property
        def is_closed(self) -> bool:
            """Is group closed."""

        async def wait_closing(self):
            """Wait until closing is ``True``."""

        async def wait_closed(self):
            """Wait until closed is ``True``."""

        def create_subgroup(self) -> 'Group':
            """Create new Group as a child of this Group. Return the new Group.

            When a parent Group gets closed, all of its children are closed.
            Closing of a subgroup has no effect on the parent Group.

            Subgroup inherits exception handler from its parent.

            """

        def wrap(self, future: asyncio.Future) -> asyncio.Task:
            """Wrap the Future into a Task and schedule its execution. Return the
            Task object.

            Resulting task is shielded and can be canceled only with
            `Group.async_close`.

            """

        def spawn(self, fn: typing.Callable[..., typing.Awaitable],
                  *args, **kwargs) -> asyncio.Task:
            """Wrap the result of a `fn` into a Task and schedule its execution.
            Return the Task object.

            Function `fn` is called with provided `args` and `kwargs`.
            Resulting Task is shielded and can be canceled only with
            `Group.async_close`.

            """

        def close(self, cancel: bool = True):
            """Schedule Group closing.

            Closing Future is set immediately. All subgroups are closed, and all
            running tasks are optionally canceled. Once closing of all subgroups
            and execution of all tasks is completed, closed Future is set.

            Tasks are canceled if `cancel` is ``True``.

            """

        async def async_close(self, cancel: bool = True):
            """Close Group and wait until closed is ``True``."""

        async def __aenter__(self): ...

        async def __aexit__(self, *args): ...

    class Resource(abc.ABC):
        """Resource with lifetime control based on `Group`."""

        @property
        @abc.abstractmethod
        def async_group(self) -> Group:
            """Group controlling resource's lifetime."""

        @property
        def is_open(self) -> bool:
            """``True`` if not closing or closed, ``False`` otherwise."""

        @property
        def is_closing(self) -> bool:
            """Is resource closing or closed."""

        @property
        def is_closed(self) -> bool:
            """Is resource closed."""

        async def wait_closing(self):
            """Wait until closing is ``True``."""

        async def wait_closed(self):
            """Wait until closed is ``True``."""

        def close(self):
            """Close resource."""

        async def async_close(self):
            """Close resource and wait until closed is ``True``."""
