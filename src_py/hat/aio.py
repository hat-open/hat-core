"""Async utility functions"""

import abc
import asyncio
import collections
import collections.abc
import concurrent.futures
import contextlib
import functools
import inspect
import logging
import signal
import sys
import typing


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

T = typing.TypeVar('T')


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
    async for i in xs:
        if fn(i):
            return i
    return default


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
    exception = None
    task = asyncio.ensure_future(f)
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as e:
            if raise_cancel:
                exception = e
        except Exception:
            pass
    if exception:
        raise exception
    return task.result()


# TODO: AsyncCallable rewrite needed
class _AsyncCallableType(type(typing.Callable), _root=True):

    def __init__(self):
        if sys.version_info[:2] == (3, 8):
            kwargs = {'origin': collections.abc.Callable,
                      'params': (..., typing.Optional[typing.Awaitable]),
                      'special': True}
        else:
            kwargs = {'origin': collections.abc.Callable,
                      'nparams': (..., typing.Optional[typing.Awaitable])}
        super().__init__(**kwargs)

    def __getitem__(self, params):
        if len(params) == 2:
            params = (params[0], typing.Union[params[1],
                                              typing.Awaitable[params[1]]])
        return super().__getitem__(params)


AsyncCallable = _AsyncCallableType()
"""Async callable"""


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
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result


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
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.Future()
    return await call(fn, *args, *kwargs)


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
    with contextlib.suppress(Exception):
        await f
    return await call(fn, *args, *kwargs)


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

    Example::

        executor1 = create_executor()
        executor2 = create_executor()
        tid1 = await executor1(threading.get_ident)
        tid2 = await executor2(threading.get_ident)
        assert tid1 != tid2

    """
    executor = executor_cls(*args)

    async def executor_wrapper(func, /, *args, **kwargs):
        _loop = loop or asyncio.get_event_loop()
        fn = functools.partial(func, *args, **kwargs)
        return await _loop.run_in_executor(executor, fn)

    return executor_wrapper


def init_asyncio(policy: typing.Optional[asyncio.AbstractEventLoopPolicy] = None):  # NOQA
    """Initialize asyncio.

    Sets event loop policy (if ``None``, instance of
    `asyncio.DefaultEventLoopPolicy` is used).

    After policy is set, new event loop is created and associated with current
    thread.

    On Windows, `asyncio.WindowsProactorEventLoopPolicy` is used as default
    policy.

    """

    def get_default_policy():
        if sys.platform == 'win32':
            return asyncio.WindowsProactorEventLoopPolicy()

        # TODO: evaluate usage of uvloop
        # with contextlib.suppress(ModuleNotFoundError):
        #     import uvloop
        #     return uvloop.EventLoopPolicy()

        return asyncio.DefaultEventLoopPolicy()

    asyncio.set_event_loop_policy(policy or get_default_policy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


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
    if create_loop:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    task = asyncio.ensure_future(future, loop=loop)

    if sys.platform == 'win32':

        async def task_wrapper(task):
            try:
                while not task.done():
                    await asyncio.wait([task], timeout=0.5)
            except asyncio.CancelledError:
                task.cancel()
            return await task

        task = asyncio.ensure_future(task_wrapper(task), loop=loop)

    if not handle_signals:
        return loop.run_until_complete(task)

    canceled = False
    signalnums = [signal.SIGINT, signal.SIGTERM]
    if sys.platform == 'win32':
        signalnums += [signal.SIGBREAK]

    def signal_handler(*args):
        nonlocal canceled
        if canceled:
            return
        loop.call_soon_threadsafe(task.cancel)
        canceled = True

    handlers = {signalnum: signal.getsignal(signalnum) or signal.SIG_DFL
                for signalnum in signalnums}
    for signalnum in signalnums:
        signal.signal(signalnum, signal_handler)

    try:
        return loop.run_until_complete(task)

    finally:
        for signalnum, handler in handlers.items():
            signal.signal(signalnum, handler)


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

    """

    def __init__(self, maxsize: int = 0):
        self._maxsize = maxsize
        self._queue = collections.deque()
        self._getters = collections.deque()
        self._putters = collections.deque()
        self._closed = asyncio.Future()

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self.get()
        except QueueClosedError:
            raise StopAsyncIteration

    def __str__(self):
        return (f'<{type(self).__name__}'
                f' _closed={self._closed.done()} '
                f' _queue={list(self._queue)}>')

    def __len__(self):
        return len(self._queue)

    @property
    def maxsize(self) -> int:
        """Maximum number of items in the queue."""
        return self._maxsize

    @property
    def is_closed(self) -> bool:
        """Is queue closed."""
        return self._closed.done()

    def empty(self) -> bool:
        """``True`` if queue is empty, ``False`` otherwise."""
        return not self._queue

    def full(self) -> bool:
        """``True`` if queue is full, ``False`` otherwise."""
        return (len(self._queue) >= self._maxsize if self._maxsize > 0
                else False)

    def qsize(self) -> int:
        """Number of items currently in the queue."""
        return len(self._queue)

    def close(self):
        """Close the queue."""
        if self._closed.done():
            return
        self._closed.set_result(True)
        self._wakeup_all(self._putters)
        self._wakeup_next(self._getters)

    def get_nowait(self) -> typing.Any:
        """Return an item if one is immediately available, else raise
        `QueueEmptyError`.

        Raises:
            QueueEmptyError

        """
        if self.empty():
            raise QueueEmptyError()
        item = self._queue.popleft()
        self._wakeup_next(self._putters)
        return item

    def put_nowait(self, item: typing.Any):
        """Put an item into the queue without blocking.

        If no free slot is immediately available, raise `QueueFullError`.

        Raises:
            QueueFullError

        """
        if self._closed.done():
            raise QueueClosedError()
        if self.full():
            raise QueueFullError()
        self._queue.append(item)
        self._wakeup_next(self._getters)

    async def get(self) -> typing.Any:
        """Remove and return an item from the queue.

        If queue is empty, wait until an item is available.

        Raises:
            QueueClosedError

        """
        while self.empty():
            if self._closed.done():
                self._wakeup_all(self._getters)
                raise QueueClosedError()
            getter = asyncio.Future()
            self._getters.append(getter)
            try:
                await getter
            except BaseException:
                getter.cancel()
                with contextlib.suppress(ValueError):
                    self._getters.remove(getter)
                if not getter.cancelled():
                    if not self.empty() or self._closed.done():
                        self._wakeup_next(self._getters)
                raise
        return self.get_nowait()

    async def put(self, item: typing.Any):
        """Put an item into the queue.

        If the queue is full, wait until a free slot is available before adding
        the item.

        Raises:
            QueueClosedError

        """
        while not self._closed.done() and self.full():
            putter = asyncio.Future()
            self._putters.append(putter)
            try:
                await putter
            except BaseException:
                putter.cancel()
                with contextlib.suppress(ValueError):
                    self._putters.remove(putter)
                if not self.full() and not putter.cancelled():
                    self._wakeup_next(self._putters)
                raise
        return self.put_nowait(item)

    async def get_until_empty(self) -> typing.Any:
        """Empty the queue and return the last item.

        If queue is empty, wait until at least one item is available.

        Raises:
            QueueClosedError

        """
        item = await self.get()
        while not self.empty():
            item = self.get_nowait()
        return item

    def get_nowait_until_empty(self) -> typing.Any:
        """Empty the queue and return the last item if at least one
        item is immediately available, else raise `QueueEmptyError`.

        Raises:
            QueueEmptyError

        """
        item = self.get_nowait()
        while not self.empty():
            item = self.get_nowait()
        return item

    def _wakeup_next(self, waiters):
        while waiters:
            waiter = waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                break

    def _wakeup_all(self, waiters):
        while waiters:
            waiter = waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)


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
                 loop: typing.Optional[asyncio.AbstractEventLoop] = None):
        self._exception_cb = exception_cb
        self._loop = loop or asyncio.get_event_loop()
        self._closing = asyncio.Future()
        self._closed = asyncio.Future()
        self._canceled = False
        self._tasks = set()
        self._parent = None
        self._children = set()

    @property
    def is_open(self) -> bool:
        """``True`` if group is not closing or closed, ``False`` otherwise."""
        return not self._closing.done()

    @property
    def is_closing(self) -> bool:
        """Is group closing or closed."""
        return self._closing.done()

    @property
    def is_closed(self) -> bool:
        """Is group closed."""
        return self._closed.done()

    async def wait_closing(self):
        """Wait until closing is ``True``."""
        await asyncio.shield(self._closing)

    async def wait_closed(self):
        """Wait until closed is ``True``."""
        await asyncio.shield(self._closed)

    def create_subgroup(self) -> 'Group':
        """Create new Group as a child of this Group. Return the new Group.

        When a parent Group gets closed, all of its children are closed.
        Closing of a subgroup has no effect on the parent Group.

        Subgroup inherits exception handler from its parent.

        """
        if self._closing.done():
            raise Exception('group not open')
        child = Group(self._exception_cb, loop=self._loop)
        child._parent = self
        self._children.add(child)
        return child

    def wrap(self,
             future: asyncio.Future
             ) -> asyncio.Task:
        """Wrap the Future into a Task and schedule its execution. Return the
        Task object.

        Resulting task is shielded and can be canceled only with
        `Group.async_close`.

        """
        if self._closing.done():
            raise Exception('group not open')
        task = asyncio.ensure_future(future, loop=self._loop)
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return asyncio.shield(task)

    def spawn(self,
              fn: typing.Callable[..., typing.Awaitable],
              *args, **kwargs
              ) -> asyncio.Task:
        """Wrap the result of a `fn` into a Task and schedule its execution.
        Return the Task object.

        Function `fn` is called with provided `args` and `kwargs`.
        Resulting Task is shielded and can be canceled only with
        `Group.async_close`.

        """
        if self._closing.done():
            raise Exception('group not open')
        future = fn(*args, **kwargs)
        return self.wrap(future)

    def close(self, cancel: bool = True):
        """Schedule Group closing.

        Closing Future is set immediately. All subgroups are closed, and all
        running tasks are optionally canceled. Once closing of all subgroups
        and execution of all tasks is completed, closed Future is set.

        Tasks are canceled if `cancel` is ``True``.

        """
        for child in list(self._children):
            child.close(cancel)
        if cancel and not self._canceled:
            self._canceled = True
            for task in self._tasks:
                self._loop.call_soon(task.cancel)
        if self._closing.done():
            return
        self._closing.set_result(True)
        futures = [*self._tasks,
                   *(child._closed for child in self._children)]
        if futures:
            waiting_future = asyncio.ensure_future(
                asyncio.wait(futures), loop=self._loop)
            waiting_future.add_done_callback(lambda _: self._on_closed())
        else:
            self._on_closed()

    async def async_close(self, cancel: bool = True):
        """Close Group and wait until closed is ``True``."""
        self.close(cancel)
        await self.wait_closed()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.async_close()

    def _on_closed(self):
        if self._parent is not None:
            self._parent._children.remove(self)
            self._parent = None
        self._closed.set_result(True)

    def _on_task_done(self, task):
        self._tasks.remove(task)
        if task.cancelled():
            return
        e = task.exception()
        if e:
            exception_cb = self._exception_cb or self._default_exception_cb
            exception_cb(e)

    def _default_exception_cb(self, e):
        mlog.warning('unhandled exception in async group: %s', e, exc_info=e)


class Resource(abc.ABC):
    """Resource with lifetime control based on `Group`."""

    @property
    @abc.abstractmethod
    def async_group(self) -> Group:
        """Group controlling resource's lifetime."""

    @property
    def is_open(self) -> bool:
        """``True`` if not closing or closed, ``False`` otherwise."""
        return self.async_group.is_open

    @property
    def is_closing(self) -> bool:
        """Is resource closing or closed."""
        return self.async_group.is_closing

    @property
    def is_closed(self) -> bool:
        """Is resource closed."""
        return self.async_group.is_closed

    async def wait_closing(self):
        """Wait until closing is ``True``."""
        await self.async_group.wait_closing()

    async def wait_closed(self):
        """Wait until closed is ``True``."""
        await self.async_group.wait_closed()

    def close(self):
        """Close resource."""
        self.async_group.close()

    async def async_close(self):
        """Close resource and wait until closed is ``True``."""
        await self.async_group.async_close()
