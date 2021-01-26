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
                    ) -> typing.Optional[T]: ...

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
                            ) -> typing.Any: ...

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

    async def call(fn: AsyncCallable, *args, **kwargs) -> typing.Any: ...

    async def call_on_cancel(fn: AsyncCallable, *args, **kwargs) -> typing.Any: ...

    async def call_on_done(f: typing.Awaitable,
                           fn: AsyncCallable,
                           *args, **kwargs
                           ) -> typing.Any: ...

When regular functions are called by `call` coroutine, result of function call
is immediately available as result of `call` coroutine. If function call results
in awaitable object (e.g. when coroutine is called in place of regular
function), resulting awaitable is awaited and its result is returned as result
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
                        ) -> typing.Callable[..., typing.Awaitable]: ...

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

    def init_asyncio(policy: typing.Optional[asyncio.AbstractEventLoopPolicy] = None): ...

    def run_asyncio(future: typing.Awaitable, *,
                    handle_signals=True,
                    create_loop=False
                    ) -> typing.Any: ...

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

    class QueueClosedError(Exception): ...

    class QueueEmptyError(Exception): ...

    class QueueFullError(Exception): ...

    class Queue:

        def __init__(self, maxsize: int = 0): ...

        def __aiter__(self): ...

        async def __anext__(self): ...

        def __str__(self): ...

        def __len__(self): ...

        @property
        def maxsize(self) -> int: ...

        @property
        def is_closed(self) -> bool: ...

        def empty(self) -> bool: ...

        def full(self) -> bool: ...

        def qsize(self) -> int: ...

        def close(self): ...

        def get_nowait(self) -> typing.Any: ...

        def put_nowait(self, item: typing.Any): ...

        async def get(self) -> typing.Any: ...

        async def put(self, item: typing.Any): ...

        async def get_until_empty(self) -> typing.Any: ...

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

    class Group:

        def __init__(self,
                     exception_cb: typing.Optional[ExceptionCb] = None,
                     *,
                     loop: typing.Optional[asyncio.AbstractEventLoop] = None): ...

        @property
        def is_open(self) -> bool: ...

        @property
        def is_closing(self) -> bool: ...

        @property
        def is_closed(self) -> bool: ...

        async def wait_closing(self): ...

        async def wait_closed(self): ...

        def create_subgroup(self) -> 'Group': ...

        def wrap(self,
                 future: asyncio.Future
                 ) -> asyncio.Task: ...

        def spawn(self,
                  fn: typing.Callable[..., typing.Awaitable],
                  *args, **kwargs
                  ) -> asyncio.Task: ...

        def close(self, cancel: bool = True): ...

        async def async_close(self, cancel: bool = True): ...

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

        @property
        @abc.abstractmethod
        def async_group(self) -> Group: ...

        @property
        def is_open(self) -> bool: ...

        @property
        def is_closing(self) -> bool: ...

        @property
        def is_closed(self) -> bool: ...

        async def wait_closing(self): ...

        async def wait_closed(self): ...

        def close(self): ...

        async def async_close(self): ...


API
---

API reference is available as part of generated documentation:

    * `Python hat.aio module <../pyhat/hat/aio.html>`_
