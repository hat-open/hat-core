import asyncio
import collections
import signal
import subprocess
import sys
import threading
import time
import unittest.mock

import pytest

from hat import aio


pytestmark = pytest.mark.asyncio


async def test_first():
    queue = aio.Queue()
    queue.put_nowait(1)
    queue.put_nowait(2)
    queue.put_nowait(3)
    queue.close()

    result = await aio.first(queue, lambda i: i == 2)
    assert result == 2

    assert not queue.empty()
    assert queue.get_nowait() == 3
    assert queue.empty()

    queue = aio.Queue()
    queue.put_nowait(1)
    queue.put_nowait(2)
    queue.put_nowait(3)
    queue.close()
    result = await aio.first(queue, lambda i: i == 4)
    assert result is None
    assert queue.empty()


async def test_first_example():

    async def async_range(x):
        for i in range(x):
            await asyncio.sleep(0)
            yield i

    assert await aio.first(async_range(3)) == 0
    assert await aio.first(async_range(3), lambda x: x > 1) == 2
    assert await aio.first(async_range(3), lambda x: x > 2) is None
    assert await aio.first(async_range(3), lambda x: x > 2, 123) == 123


async def test_first_example_docs():
    queue = aio.Queue()
    queue.put_nowait(1)
    queue.put_nowait(2)
    queue.put_nowait(3)
    queue.close()

    assert 1 == await aio.first(queue)
    assert 3 == await aio.first(queue, lambda x: x > 2)
    assert 123 == await aio.first(queue, default=123)


async def test_uncancellable():
    f1 = asyncio.Future()

    async def f():
        return await f1

    f2 = aio.uncancellable(f(), raise_cancel=False)
    f3 = asyncio.ensure_future(f2)
    asyncio.get_event_loop().call_soon(f3.cancel)
    f1.set_result(123)
    result = await f3
    assert result == 123


async def test_uncancellable_exception():
    f1 = asyncio.Future()
    e = Exception()

    async def f():
        await asyncio.sleep(0)
        return await f1

    f2 = aio.uncancellable(f(), raise_cancel=False)
    f3 = asyncio.ensure_future(f2)
    asyncio.get_event_loop().call_soon(f3.cancel)
    f1.set_exception(e)
    try:
        await f3
    except Exception as ex:
        exc = ex
    assert exc is e


async def test_uncancellable_vs_shield():

    async def set_future(f, value):
        await asyncio.sleep(0.001)
        f.set_result(value)

    future = asyncio.Future()
    t1 = asyncio.shield(set_future(future, 1))
    t2 = asyncio.ensure_future(t1)
    asyncio.get_event_loop().call_soon(t2.cancel)
    with pytest.raises(asyncio.CancelledError):
        await t2
    assert not future.done()
    await future
    assert future.result() == 1

    future = asyncio.Future()
    t1 = aio.uncancellable(set_future(future, 1), raise_cancel=True)
    t2 = asyncio.ensure_future(t1)
    asyncio.get_event_loop().call_soon(t2.cancel)
    with pytest.raises(asyncio.CancelledError):
        await t2
    assert future.done()
    assert future.result() == 1

    future = asyncio.Future()
    t1 = aio.uncancellable(set_future(future, 1), raise_cancel=False)
    t2 = asyncio.ensure_future(t1)
    asyncio.get_event_loop().call_soon(t2.cancel)
    await t2
    assert future.done()
    assert future.result() == 1


async def test_call():

    def f1(x):
        return x

    async def f2(x):
        await asyncio.sleep(0)
        return x

    result = await aio.call(f1, 123)
    assert result == 123

    result = await aio.call(f2, 123)
    assert result == 123


async def test_call_on_cancel():
    exceptions = aio.Queue()
    called = asyncio.Future()
    group = aio.Group(exceptions.put_nowait)

    async def closing(called):
        called.set_result(True)
        assert group.is_closing
        assert not group.is_closed

    group.spawn(aio.call_on_cancel, closing, called)
    assert not called.done()

    await group.async_close()
    assert called.done()
    assert exceptions.empty()


async def test_call_on_cancel_example():
    f = asyncio.Future()
    group = aio.Group()
    group.spawn(aio.call_on_cancel, f.set_result, 123)
    assert not f.done()
    await group.async_close()
    assert f.result() == 123


async def test_call_on_done():
    f1 = asyncio.Future()
    f2 = asyncio.Future()
    f3 = asyncio.ensure_future(aio.call_on_done(f1, f2.set_result, 123))

    await asyncio.sleep(0)
    assert not f1.done()
    assert not f2.done()
    assert not f3.done()

    f1.set_result(None)
    await asyncio.wait_for(f3, 0.001)
    assert f2.result() == 123
    assert f3.result() is None


async def test_call_on_done_example():
    f = asyncio.Future()
    group = aio.Group()
    group.spawn(aio.call_on_done, f, group.close)
    assert group.is_open
    f.set_result(None)
    await group.wait_closed()
    assert group.is_closed


async def test_wait_for(event_loop):

    async def return_result(delay):
        await asyncio.sleep(delay)
        return 123

    async def raise_exception(delay):
        await asyncio.sleep(delay)
        raise Exception()

    result = await aio.wait_for(return_result(0), 0.001)
    assert result == 123

    with pytest.raises(Exception):
        await aio.wait_for(raise_exception(0), 0.001)

    with pytest.raises(asyncio.TimeoutError):
        await aio.wait_for(return_result(0.001), 0)

    f = asyncio.ensure_future(aio.wait_for(return_result(0.001), 0))
    event_loop.call_soon(f.cancel)
    with pytest.raises(asyncio.CancelledError):
        await f

    async def f1():
        try:
            await aio.wait_for(return_result(0), 0.001)
        except aio.CancelledWithResultError as e:
            assert e.result == 123
            assert e.exception is None
        else:
            assert False

    f = asyncio.ensure_future(f1())
    event_loop.call_soon(f.cancel)
    await f

    async def f2():
        try:
            await aio.wait_for(raise_exception(0), 0.001)
        except aio.CancelledWithResultError as e:
            assert e.result is None
            assert e.exception is not None
        else:
            assert False

    f = asyncio.ensure_future(f2())
    event_loop.call_soon(f.cancel)
    await f


async def test_create_executor():
    executor = aio.create_executor()
    result = await executor(lambda: threading.current_thread().name)
    assert threading.current_thread().name != result


async def test_create_executor_example():
    executor1 = aio.create_executor()
    executor2 = aio.create_executor()
    tid1 = await executor1(threading.get_ident)
    tid2 = await executor2(threading.get_ident)
    assert tid1 != tid2


@pytest.mark.skipif(sys.platform == 'win32',
                    reason="pthread_kill not supported")
def test_run_asyncio():
    ident = threading.get_ident()

    def thread():
        time.sleep(0.01)
        signal.pthread_kill(ident, signal.SIGINT)

    t = threading.Thread(target=thread)
    t.start()

    async def f():
        await asyncio.Future()

    with pytest.raises(asyncio.CancelledError):
        aio.run_asyncio(f())
    t.join()


# TODO check implementation for posible deadlock
def test_run_asyncio_with_subprocess(tmp_path):

    py_path = tmp_path / 'temp.py'
    run_path = tmp_path / 'temp.run'
    with open(py_path, 'w', encoding='utf-8') as f:
        f.write(f"from hat import aio\n"
                f"import asyncio\n"
                f"import sys\n"
                f"async def f():\n"
                f"    open(r'{run_path}', 'w').close()\n"
                f"    await asyncio.Future()\n"
                f"try:\n"
                f"    aio.run_asyncio(f())\n"
                f"except asyncio.CancelledError:\n"
                f"    sys.exit(0)\n"
                f"except Exception:\n"
                f"    sys.exit(10)\n"
                f"sys.exit(5)\n")

    p = subprocess.Popen([sys.executable, str(py_path)],
                         creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                                        if sys.platform == 'win32' else 0))
    while not run_path.exists():
        assert p.poll() is None
        time.sleep(0.01)
    p.send_signal(signal.CTRL_BREAK_EVENT
                  if sys.platform == 'win32'
                  else signal.SIGINT)
    assert p.wait() == 0


@pytest.mark.skipif(sys.platform == 'win32',
                    reason="pthread_kill not supported")
def test_run_asyncio_with_multiple_signals():
    ident = threading.get_ident()

    def thread():
        time.sleep(0.01)
        for _ in range(5):
            signal.pthread_kill(ident, signal.SIGINT)
            time.sleep(0.001)

    t = threading.Thread(target=thread)
    t.start()

    async def f():
        await aio.uncancellable(asyncio.sleep(0.02), raise_cancel=False)
        return 1

    assert aio.run_asyncio(f()) == 1
    t.join()


# TODO: test run_asyncio with `handle_signals` and `create_loop`


def test_run_async_example():

    async def run():
        await asyncio.sleep(0)
        return 123

    result = aio.run_asyncio(run())
    assert result == 123


async def test_queue():
    queue = aio.Queue()
    assert not queue.is_closed
    f = asyncio.ensure_future(queue.get())
    assert not f.done()
    queue.put_nowait(1)
    assert 1 == await f
    for _ in range(5):
        queue.close()
        assert queue.is_closed
    with pytest.raises(aio.QueueClosedError):
        await queue.get()


def test_queue_str():
    queue = aio.Queue()
    result = str(queue)
    assert isinstance(result, str)
    assert result


def test_queue_len():
    count = 10
    queue = aio.Queue()
    assert len(queue) == 0

    for i in range(count):
        queue.put_nowait(None)
        assert len(queue) == i + 1
        assert queue.qsize() == i + 1

    for i in range(count):
        queue.get_nowait()
        assert queue.qsize() == count - i - 1

    assert len(queue) == 0


def test_queue_get_nowait():
    queue = aio.Queue()
    with pytest.raises(aio.QueueEmptyError):
        queue.get_nowait()


async def test_queue_get_until_empty():
    queue = aio.Queue()
    queue.put_nowait(1)
    queue.put_nowait(2)
    queue.put_nowait(3)
    result = await queue.get_until_empty()
    assert result == 3


def test_queue_get_nowait_until_empty():
    queue = aio.Queue()
    queue.put_nowait(1)
    queue.put_nowait(2)
    queue.put_nowait(3)
    result = queue.get_nowait_until_empty()
    assert result == 3


async def test_queue_with_size():
    queue_size = 5
    queue = aio.Queue(queue_size)
    assert queue.maxsize == queue_size

    for _ in range(queue_size):
        queue.put_nowait(None)

    with pytest.raises(aio.QueueFullError):
        queue.put_nowait(None)


async def test_queue_put():
    queue = aio.Queue(1)
    await queue.put(1)
    put_future = asyncio.ensure_future(queue.put(1))
    asyncio.get_event_loop().call_soon(queue.close)
    with pytest.raises(aio.QueueClosedError):
        await put_future


async def test_queue_put_cancel():
    queue = aio.Queue(1)
    await queue.put(0)
    f1 = asyncio.ensure_future(queue.put(1))
    f2 = asyncio.ensure_future(queue.put(2))
    await asyncio.sleep(0)
    assert 0 == queue.get_nowait()
    f1.cancel()
    assert 2 == await queue.get()
    with pytest.raises(asyncio.CancelledError):
        await f1
    await f2


@pytest.mark.parametrize('item_count', [0, 1, 2, 10])
async def test_queue_async_iterable(item_count):
    queue = aio.Queue()
    data = collections.deque()

    for i in range(10):
        queue.put_nowait(i)
        data.append(i)

    asyncio.get_running_loop().call_later(0.001, queue.close)

    async for i in queue:
        assert i == data.popleft()

    assert queue.empty()
    assert len(data) == 0


async def test_queue_get_canceled():
    queue = aio.Queue()
    f1 = asyncio.ensure_future(queue.get())
    f2 = asyncio.ensure_future(queue.get())
    await asyncio.sleep(0)
    queue.put_nowait(123)
    f1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await f1
    assert 123 == await f2


async def test_queue_example():
    queue = aio.Queue(maxsize=1)

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


async def test_group():
    group = aio.Group()
    futures = [group.wrap(asyncio.Future()) for _ in range(100)]
    assert not any(future.done() for future in futures)
    await group.async_close()
    assert all(future.done() for future in futures)
    assert not group.is_open
    assert group.is_closing
    assert group.is_closed
    await group.wait_closing()
    await group.wait_closed()


async def test_group_spawn_async_close():

    async def task():
        group.spawn(group.async_close)
        await asyncio.Future()

    group = aio.Group()
    group.spawn(task)
    await group.wait_closed()


async def test_group_subgroup():
    g1 = aio.Group()
    g2 = g1.create_subgroup()
    f = g2.wrap(asyncio.Future())
    g1.close()

    assert g1.is_closing
    assert g2.is_closing
    assert not f.done()
    assert not g1.is_closed
    assert not g2.is_closed

    with pytest.raises(Exception):
        g1.create_subgroup()
    await g1.async_close()
    with pytest.raises(Exception):
        g1.create_subgroup()

    assert f.done()
    assert g1.is_closed
    assert g2.is_closed


async def test_group_async_close_subgroup_without_tasks():
    g1 = aio.Group()
    g2 = g1.create_subgroup()
    await g1.async_close()

    assert g1.is_closed
    assert g2.is_closed


async def test_group_spawn_subgroup_in_closing_subgroup():
    exceptions = aio.Queue()
    g1 = aio.Group(lambda e: exceptions.put_nowait(e))
    g2 = g1.create_subgroup()

    async def task():
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            with pytest.raises(Exception):
                g1.create_subgroup()

    g2.spawn(task)
    await g1.async_close()
    assert g1.is_closed
    assert g2.is_closed
    assert exceptions.empty()


async def test_group_spawn_when_not_open():
    g = aio.Group()
    g.spawn(asyncio.Future)
    g.close()
    with pytest.raises(Exception):
        g.spawn(asyncio.Future)
    await g.async_close()
    with pytest.raises(Exception):
        g.spawn(asyncio.Future)
    with pytest.raises(Exception):
        g.wrap(asyncio.Future())


def test_group_close_empty_group():
    g = aio.Group()
    assert not g.is_closing
    assert not g.is_closed
    g.close()
    assert g.is_closing
    assert g.is_closed


async def test_group_context():
    async with aio.Group() as g:
        f = g.spawn(asyncio.Future)
        assert not f.done()
    assert f.done()


async def test_group_custom_exception_handler():

    def exception_cb(e):
        nonlocal e2
        e2 = e

    async def f():
        raise e1

    e1 = Exception()
    e2 = None
    g = aio.Group(exception_cb)
    with pytest.raises(Exception):
        await g.spawn(f)
    await g.async_close()

    assert e1 is e2


async def test_group_default_exception_handler():

    async def f():
        raise e

    e = Exception()
    g = aio.Group()
    with unittest.mock.patch('hat.aio.mlog.warning') as mock:
        with pytest.raises(Exception):
            await g.spawn(f)
    await g.async_close()

    _, kwargs = mock.call_args
    assert kwargs['exc_info'] is e


async def test_group_example_docs_spawn():

    async def f1(x):
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            return x

    async def f2(x):
        await asyncio.sleep(0)
        return x

    async with aio.Group() as group:
        f = group.spawn(f1, 'f1')
        assert 'f2' == await group.spawn(f2, 'f2')
    assert 'f1' == await f


async def test_group_example_docs_subgroup():
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


async def test_resource():

    class Mock(aio.Resource):

        def __init__(self):
            self._async_group = aio.Group()
            self._async_group.spawn(asyncio.sleep, 1)

        @property
        def async_group(self):
            return self._async_group

    mock = Mock()
    assert mock.is_open
    assert not mock.is_closing
    assert not mock.is_closed

    mock.close()
    assert not mock.is_open
    assert mock.is_closing
    assert not mock.is_closed

    await mock.wait_closing()
    await mock.wait_closed()
    assert not mock.is_open
    assert mock.is_closing
    assert mock.is_closed

    await mock.async_close()
