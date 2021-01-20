.. _hat-aio:

`hat.aio` - Python asyncio utility library
==========================================

Additional functions/coroutines that enhance Python `asyncio` library. For more
information on `asyncio` see
`Python standard library documentation <https://docs.python.org/3/library/asyncio.html>`_.


.. _hat-aio-fist:

`hat.aio.first`
---------------

Same as :ref:`hat.util.first <hat-util-first>` where `Iterable` is replaced
with `AsyncIterable`::

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

        """

This coroutine can be used on any kind of async iterable including
:ref:`hat.aio.Queue <hat-aio-Queue>`::

    queue = Queue()
    queue.put_nowait(1)
    queue.put_nowait(2)
    queue.put_nowait(3)
    queue.close()

    assert 1 == await first(queue)
    assert 3 == await first(queue, lambda x: x > 2)
    assert 123 == await first(queue, default=123)


.. _hat-aio-uncancellable:

`hat.aio.uncancellable`
-----------------------

This coroutine provides enhancement of `asyncio.shield` mechanism.
`asyncio.shield` provides canceling protection for shielded future but
interrupts execution of task which awaited for shielded future. By using
`uncancellable`, future can be shielded from cancellation with addition
of suspending cancellation of task awaiting shielded future. This cancellation
is suspended until shielded future is done (if `raise_cancel` is ``True``) or
is completely ignored (if `raise_cancel` is ``False``). Calling
`uncancellable` with `raise_cancel` set to ``False`` should be used with extra
caution because it disrupts usual `asyncio.CancelledError` propagation.

::

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

Most significant usage of this coroutine is in scenarios where cancellation
of task should be temporary suspended until internally acquired resources are
released::

    async def create_resource(): ...

    async def consume_resource(resource): ...

    async def free_resource(resource): ...

    async def run():
        resource = await create_resource()
        try:
            await consume_resource(resource)
        finally:
            await uncancellable(free_resource(resource))


.. _hat-aio-call:
.. _hat-aio-call_on_cancel:
.. _hat-aio-call_on_done:

`hat.aio.call`, `hat.aio.call_on_cancel` and `hat.aio.call_on_done`
-------------------------------------------------------------------

`call`, `call_on_cancel` and `call_on_done` provide the same mechanism for
function and coroutine calling::

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

        """

When regular functions are called by `call` coroutine, result of function call
is immediately available as result of `call` coroutine. If function call results
in awaitable object (e.g. when coroutine is called in place of regular
function), resulting awaitable is awaited and it's result is returned as result
of `call` coroutine::

    def f1(x):
        return x

    async def f2(x):
        await asyncio.sleep(0)
        return x

    result = await call(f1, 123)
    assert result == 123

    result = await call(f2, 123)
    assert result == 123

`call_on_cancel` coroutine waits until its execution is cancelled (until
asyncio.CancelledError is raised) and then executes provided callable with
`call` coroutine. This behavior is most useful in combination with
:ref:`hat.aio.Goup <hat-aio-Group>`'s `spawn` method::

    f = asyncio.Future()
    group = Group()
    group.spawn(call_on_cancel, f.set_result, 123)
    await group.async_close()
    assert f.result() == 123

`call_on_done` coroutine accepts additional future which is awaited prior to
application of `call` coroutine. Same as `call_on_cancel`, it is usually
used with :ref:`hat.aio.Goup <hat-aio-Group>`'s `spawn` method::

    f = asyncio.Future()
    group = Group()
    group.spawn(call_on_done, f, group.close)
    f.set_result(None)
    await group.wait_closed()


.. _hat-aio-create_executor:

`hat.aio.create_executor`
-------------------------

This helper coroutine provides simple wrapper for creation of executor
instances and invocation of `asyncio.loop.run_in_executor` coroutine::

    def create_executor(*args: typing.Any,
                        executor_cls: typing.Type = concurrent.futures.ThreadPoolExecutor,  # NOQA
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

        """

Example usage::

    executor1 = create_executor()
    executor2 = create_executor()
    tid1 = await executor1(threading.get_ident)
    tid2 = await executor2(threading.get_ident)
    assert tid1 != tid2


.. _hat-aio-init_asyncio:
.. _hat-aio-run_asyncio:

`hat.aio.init_asyncio` and `hat.aio.run_asyncio`
------------------------------------------------

Utility coroutines for initialization of asyncio loop and task execution::

    def init_asyncio(policy: typing.Optional[asyncio.AbstractEventLoopPolicy] = None):  # NOQA
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

        """

Example usage::

    def main():
        init_asyncio()
        result = run_asyncio(async_main())
        assert result == 123

    async def async_main():
        await asyncio.sleep(0)
        return 123

    if __name__ == '__main__':
        main()


.. _hat-aio-Queue:

`hat.aio.Queue`
---------------

`hat.aio.Queue` provides drop-in replacement for
`asyncio.Queue <https://docs.python.org/3/library/asyncio-queue.html>`_ with
addition of `close` method. Once queue is closed, all future calls to `put`
methods will result in raising of `QueueClosedError`. Once queue is closed and
empty, all future calls to `get` methods will also result in raising of
`QueueClosedError`.

::

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

Example usage::

    queue = Queue(maxsize=1)

    async def producer():
        for i in range(4):
            await queue.put(i)
        queue.close()

    async def consumer():
        result = 0
        async for i in queue:
            result += i
        return result

    asyncio.ensure_future(producer())
    result = await consumer()
    assert result == 6


.. _hat-aio-Group:

`hat.aio.Group`
---------------

`Group` provides mechanics for `safe` task execution and life-time control::

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

In most basic use-case, `Group`'s `spawn` method can be used as `safer`
wrapper for `asyncio.ensure_future`::

    async def f1(x):
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            return x

    async def f2(x):
        await asyncio.sleep(0)
        return x

    async with Group() as group:
        f = group.spawn(f1, 'f1')
        assert 'f2' == await group.spawn(f2, 'f2')
    assert 'f1' == await f

`Group`'s `create_subgroup` method provides possibility of group hierarchies
for easier control of complex task execution::

    group = aio.Group()
    subgroup1 = group.create_subgroup()
    subgroup2 = group.create_subgroup()

    f1 = subgroup1.spawn(asyncio.Future)
    f2 = subgroup2.spawn(asyncio.Future)

    assert not f1.done()
    assert not f2.done()

    await group.async_close()

    assert f1.done()
    assert f2.done()


.. _hat-aio-Resource:

`hat.aio.Resource`
------------------

Simple abstract base class providing abstraction of lifetime control based on
:ref:`hat.aio.Group <hat-aio-Group>`. Lifetime states of resource (`is_open`,
`is_closing` and `is_closed`) are matching to associated group states::

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


API
---

API reference is available as part of generated documentation:

    * `Python hat.aio module <../pyhat/hat/aio.html>`_
