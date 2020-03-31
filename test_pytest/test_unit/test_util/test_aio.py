import asyncio
import builtins
import collections
import signal
import subprocess
import sys
import threading
import time
import unittest.mock

import pytest

from hat.util import aio


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_queue():
    queue = aio.Queue()
    assert not queue.closed.done()
    f = asyncio.ensure_future(queue.get())
    assert not f.done()
    queue.put_nowait(1)
    assert 1 == await f
    for _ in range(5):
        queue.close()
        assert queue.closed.done()
    with pytest.raises(aio.QueueClosedError):
        await queue.get()


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_queue_with_size():
    queue_size = 5
    queue = aio.Queue(queue_size)
    assert queue.maxsize == queue_size

    for _ in range(queue_size):
        queue.put_nowait(None)

    with pytest.raises(aio.QueueFullError):
        queue.put_nowait(None)


@pytest.mark.asyncio
async def test_queue_put():
    queue = aio.Queue(1)
    await queue.put(1)
    put_future = asyncio.ensure_future(queue.put(1))
    asyncio.get_event_loop().call_soon(queue.close)
    with pytest.raises(aio.QueueClosedError):
        await put_future


@pytest.mark.asyncio
async def test_queue_put_cancel():
    queue = aio.Queue(1)
    await queue.put(1)
    put_future = asyncio.ensure_future(queue.put(1))
    asyncio.get_event_loop().call_soon(put_future.cancel)
    with pytest.raises(asyncio.CancelledError):
        await put_future


@pytest.mark.asyncio
async def test_queue_async_iterable():
    queue = aio.Queue()
    data = collections.deque()

    for i in range(10):
        queue.put_nowait(i)
        data.append(i)

    queue.close()

    async for i in queue:
        assert i == data.popleft()

    assert queue.empty()
    assert len(data) == 0


def test_init_asyncio_without_libuv(monkeypatch):

    def invalid_import(*args, **kwargs):
        raise ModuleNotFoundError

    platform = sys.platform
    with monkeypatch.context() as ctx:
        ctx.setattr(sys, 'platform', 'win32')
        ctx.setattr(builtins, '__import__', invalid_import)
        if platform == 'win32':
            aio.init_asyncio()
        else:
            with pytest.raises(AttributeError):
                aio.init_asyncio()


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
        f.write(f"from hat.util import aio\n"
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

    p = subprocess.Popen(['python', str(py_path)],
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_call_on_cancel():
    exceptions = aio.Queue()
    called = asyncio.Future()
    group = aio.Group(exceptions.put_nowait)

    async def closing(called):
        called.set_result(True)
        assert group.closing.done()
        assert not group.closed.done()

    group.spawn(aio.call_on_cancel, closing, called)
    assert not called.done()

    await group.async_close()
    assert called.done()
    assert exceptions.empty()


@pytest.mark.asyncio
async def test_group():
    group = aio.Group()
    futures = [group.wrap(asyncio.Future()) for _ in range(100)]
    assert not any(future.done() for future in futures)
    await group.async_close()
    assert all(future.done() for future in futures)


@pytest.mark.asyncio
async def test_group_spawn_async_close():

    async def task():
        group.spawn(group.async_close)
        await asyncio.Future()

    group = aio.Group()
    group.spawn(task)
    await group.closed


@pytest.mark.asyncio
async def test_group_subgroup():
    g1 = aio.Group()
    g2 = g1.create_subgroup()
    f = g2.wrap(asyncio.Future())
    g1.close()

    assert g1.closing.done()
    assert g2.closing.done()
    assert not f.done()
    assert not g1.closed.done()
    assert not g2.closed.done()

    with pytest.raises(Exception):
        g1.create_subgroup()
    await g1.async_close()
    with pytest.raises(Exception):
        g1.create_subgroup()

    assert f.done()
    assert g1.closed.done()
    assert g2.closed.done()


@pytest.mark.asyncio
async def test_group_async_close_subgroup_without_tasks():
    g1 = aio.Group()
    g2 = g1.create_subgroup()
    await g1.async_close()

    assert g1.closed.done()
    assert g2.closed.done()


@pytest.mark.asyncio
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
    assert g1.closed.done()
    assert g2.closed.done()
    assert exceptions.empty()


@pytest.mark.asyncio
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
    assert not g.closing.done()
    assert not g.closed.done()
    g.close()
    assert g.closing.done()
    assert g.closed.done()


@pytest.mark.asyncio
async def test_group_context():
    async with aio.Group() as g:
        f = g.spawn(asyncio.Future)
        assert not f.done()
    assert f.done()


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_group_default_exception_handler():

    async def f():
        raise e

    e = Exception()
    g = aio.Group()
    with unittest.mock.patch('hat.util.aio.mlog.warning') as mock:
        with pytest.raises(Exception):
            await g.spawn(f)
    await g.async_close()

    _, kwargs = mock.call_args
    assert kwargs['exc_info'] is e


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_executor():
    executor = aio.create_executor()
    result = await executor(lambda: threading.current_thread().name)
    assert threading.current_thread().name != result
