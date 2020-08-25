"""Async utility functions

Attributes:
    mlog (logging.Logger): module logger

"""

import asyncio
import collections
import collections.abc
import concurrent.futures
import contextlib
import inspect
import itertools
import logging
import signal
import sys
import typing


mlog = logging.getLogger(__name__)


T = typing.TypeVar('T')


async def first(xs: typing.AsyncIterable[T],
                fn: typing.Callable[[T], bool] = lambda _: True,
                default: typing.Optional[T] = None) -> typing.Optional[T]:
    """Return the first element from async iterable that satisfies
    predicate `fn`, or `default` if no such element exists.

    Args:
        xs: async collection
        fn: predicate
        default: default value

    """
    async for i in xs:
        if fn(i):
            return i
    return default


async def uncancellable(f: asyncio.Future,
                        raise_cancel: bool = True) -> typing.Any:
    """Uncancellable execution of a Future.

    Future is shielded and its execution cannot be interrupted.

    If `raise_cancel` is `True` and the Future gets canceled,
    :exc:`asyncio.CancelledError` is reraised after the Future finishes.

    Warning:
        If `raise_cancel` is `False`, this method suppresses
        :exc:`asyncio.CancelledError` and stops its propagation. Use with
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


class _AsyncCallableType(type(typing.Callable), _root=True):

    def __init__(self):
        super().__init__(origin=collections.abc.Callable,
                         params=(..., typing.Optional[typing.Awaitable]),
                         special=True)

    def __getitem__(self, params):
        if len(params) == 2:
            params = (params[0], typing.Union[params[1],
                                              typing.Awaitable[params[1]]])
        return super().__getitem__(params)


AsyncCallable = _AsyncCallableType()
"""Async callable"""


async def call(fn: AsyncCallable, *args, **kwargs) -> typing.Any:
    """Call a function or a coroutine (or other callable object).

    Call a `fn` with `args` and `kwargs`. If result of this call is awaitable,
    it is awaited and returned. Otherwise, result is immediately returned.

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
            return 'x

        assert 'f1' == await hat.util.aio.call(f1, 'f1')
        assert 'f2' == await hat.util.aio.call(f2, 'f2')
        assert 'f3' == await hat.util.aio.call(f3, 'f3')

    """
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result


async def call_on_cancel(fn: AsyncCallable, *args, **kwargs) -> typing.Any:
    """Call a function or a coroutine when canceled.

    When canceled, `fn` is called with `args` and `kwargs`by using
    :func:`call`.

    Args:
        fn: function or coroutine
        args: additional function arguments
        kwargs: additional function keyword arguments

    Returns:
        function result

    """
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.Future()
    return await call(fn, *args, *kwargs)


def create_executor(*args: typing.Any,
                    executor_cls: typing.Type = concurrent.futures.ThreadPoolExecutor,  # NOQA
                    loop: typing.Optional[asyncio.AbstractEventLoop] = None
                    ) -> typing.Coroutine:
    """Create :meth:`asyncio.loop.run_in_executor` wrapper.

    Returns a coroutine that takes a function and its arguments, executes the
    function using executor created from `executor_cls` and `args`; and
    returns the result.

    Args:
        args: executor args
        executor_cls: executor class
        loop: asyncio loop

    Returns:
        Coroutine[[Callable,...],Any]: executor coroutine

    """
    executor = executor_cls(*args)

    async def executor_wrapper(fn, *fn_args):
        _loop = loop or asyncio.get_event_loop()
        return await _loop.run_in_executor(executor, fn, *fn_args)

    return executor_wrapper


def init_asyncio():
    """Initialize asyncio.

    Sets event loop policy to :class:`uvloop.EventLoopPolicy` if possible.

    On Windows, sets policy to :class:`asyncio.WindowsProactorEventLoopPolicy`.

    """
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ModuleNotFoundError:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(
                asyncio.WindowsProactorEventLoopPolicy())


def run_asyncio(future: typing.Awaitable) -> typing.Any:
    """Run asyncio loop until the `future` is completed and return the result.

    SIGINT and SIGTERM handlers are temporarily overridden. Instead of raising
    ``KeyboardInterrupt`` on every signal reception, Future is canceled only
    once. Additional signals are ignored.

    On Windows, SIGBREAK (CTRL_BREAK_EVENT) handler is also overridden and
    asyncio loop gets periodically woken up (every 0.5 seconds).

    Args:
        future: future or coroutine

    Returns:
        future's result

    """
    loop = asyncio.get_event_loop()
    task = asyncio.ensure_future(future, loop=loop)
    canceled = False
    signalnums = [signal.SIGINT, signal.SIGTERM]

    if sys.platform == 'win32':

        signalnums += [signal.SIGBREAK]

        async def task_wrapper(task):
            try:
                while not task.done():
                    await asyncio.wait([task], timeout=0.5)
            except asyncio.CancelledError:
                task.cancel()
            return await task

        task = asyncio.ensure_future(task_wrapper(task), loop=loop)

    def signal_handler(*args):
        nonlocal canceled
        if canceled:
            return
        loop.call_soon_threadsafe(task.cancel)
        canceled = True

    @contextlib.contextmanager
    def change_signal_handlers():
        handlers = {signalnum: signal.getsignal(signalnum) or signal.SIG_DFL
                    for signalnum in signalnums}
        for signalnum in signalnums:
            signal.signal(signalnum, signal_handler)
        yield
        for signalnum, handler in handlers.items():
            signal.signal(signalnum, handler)

    with change_signal_handlers():
        return loop.run_until_complete(task)


class QueueClosedError(Exception):
    """Raised when trying to use a closed queue."""


class QueueEmptyError(Exception):
    """Raised if queue is empty."""


class QueueFullError(Exception):
    """Raised if queue is full."""


class Queue:
    """Asyncio queue which implements AsyncIterable and can be closed.

    Interface and implementation are based on :class:`asyncio.Queue`.

    If `maxsize` is less than or equal to zero, the queue size is infinite.

    Args:
        maxsize: maximum number of items in the queue

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
    def closed(self) -> asyncio.Future:
        """Closed future."""
        return asyncio.shield(self._closed)

    def empty(self) -> bool:
        """`True` if queue is empty, `False` otherwise."""
        return not self._queue

    def full(self) -> bool:
        """`True` if queue is full, `False` otherwise."""
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
        :exc:`QueueEmptyError`.

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

        If no free slot is immediately available, raise :exc:`QueueFullError`.

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
        item is immediately available, else raise :exc:`QueueEmptyError`.

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


class Group:
    """Group of asyncio Tasks.

    Group enables creation and management of related asyncio Tasks. The
    Group ensures uninterrupted execution of Tasks and Task completion upon
    Group closing.

    Group can contain subgroups, which are independent Groups managed by the
    parent Group.

    If a Task raises exception, other Tasks continue to execute.

    If `exception_cb` handler is `None`, exceptions are logged with level
    WARNING.

    Args:
        exception_cb: exception handler
        loop: asyncio loop

    """

    def __init__(self,
                 exception_cb: typing.Optional[typing.Callable[[Exception], None]] = None,  # NOQA
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
        """`True` if group is not closing or closed, `False` otherwise."""
        return not self._closing.done()

    @property
    def closing(self) -> asyncio.Future:
        """Closing Future."""
        return asyncio.shield(self._closing)

    @property
    def closed(self) -> asyncio.Future:
        """Closed Future."""
        return asyncio.shield(self._closed)

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

    def wrap(self, future: asyncio.Future) -> asyncio.Task:
        """Wrap the Future into a Task and schedule its execution. Return the
        Task object.

        Resulting task is shielded and can be canceled only with
        :meth:`Group.async_close`.

        """
        if self._closing.done():
            raise Exception('group not open')
        task = asyncio.ensure_future(future, loop=self._loop)
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return asyncio.shield(task)

    def spawn(self, fn: typing.Callable[..., typing.Awaitable],
              *args, **kwargs) -> asyncio.Task:
        """Wrap the result of a `fn` into a Task and schedule its execution.
        Return the Task object.

        Function is called with provided `args` and `kwargs`.
        Resulting Task is shielded and can be canceled only with
        :meth:`Group.async_close`.

        Args:
            fn: function
            args: function arguments
            kwargs: function keyword arguments

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

        Args:
            cancel: cancel running tasks

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
        futures = list(itertools.chain(
            self._tasks,
            (child.closed for child in self._children)))
        if futures:
            waiting_future = asyncio.ensure_future(
                asyncio.wait(futures), loop=self._loop)
            waiting_future.add_done_callback(lambda _: self._on_closed())
        else:
            self._on_closed()

    async def async_close(self, cancel: bool = True):
        """Close Group and wait until closed Future is completed.

        Args:
            cancel: cancel running tasks

        """
        self.close(cancel)
        await self.closed

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
