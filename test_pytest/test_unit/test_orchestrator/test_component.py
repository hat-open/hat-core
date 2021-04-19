import asyncio
import unittest.mock
import sys

import pytest

from hat import aio
from hat.orchestrator.component import (Status,
                                        Component)


pytestmark = pytest.mark.asyncio


@pytest.fixture()
def process_queue(event_loop, monkeypatch):
    queue = aio.Queue()
    create_subprocess_exec = asyncio.create_subprocess_exec

    async def mock(*args, **kwargs):
        p = await create_subprocess_exec(*args, **kwargs)
        queue.put_nowait(p)
        return p

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', mock)
    return queue


def create_component_with_status_queue(conf):
    component = Component(conf)
    status_queue = aio.Queue()
    component.register_change_cb(
        lambda: status_queue.put_nowait(component.status))
    return component, status_queue


async def test_delayed_start_stop():
    component, status_queue = create_component_with_status_queue({
        'name': 'comp-xy',
        'args': [sys.executable, '-c', 'import time; time.sleep(30)'],
        'delay': 0.01,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    assert component.status == Status.DELAYED
    assert (await status_queue.get() == Status.STARTING)
    assert (await status_queue.get() == Status.RUNNING)
    component.stop()
    assert (await status_queue.get() == Status.STOPPING)
    assert (await status_queue.get() == Status.STOPPED)
    component.start()
    assert (await status_queue.get() == Status.STARTING)
    assert (await status_queue.get() == Status.RUNNING)
    assert status_queue.empty()
    await component.async_close()
    assert component.is_closed


async def test_revive_on_stop():
    component, status_queue = create_component_with_status_queue({
        'name': 'comp-xy',
        'args': [sys.executable, '-c', 'import time; time.sleep(30)'],
        'delay': 0,
        'revive': True,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    assert component.status == Status.STOPPED
    assert (await status_queue.get() == Status.STARTING)
    assert (await status_queue.get() == Status.RUNNING)
    for i in range(3):
        component.stop()
        assert (await status_queue.get() == Status.STOPPING)
        assert (await status_queue.get() == Status.STOPPED)
        assert (await status_queue.get() == Status.STARTING)
        assert (await status_queue.get() == Status.RUNNING)
    component.set_revive(False)
    await status_queue.get()
    component.stop()
    assert (await status_queue.get() == Status.STOPPING)
    assert (await status_queue.get() == Status.STOPPED)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(status_queue.get(), timeout=0.01)
    component.set_revive(True)
    await status_queue.get()
    assert (await status_queue.get() == Status.STARTING)
    assert (await status_queue.get() == Status.RUNNING)
    assert status_queue.empty()
    await component.async_close()
    assert component.is_closed


async def test_revive_on_component_finish():
    component, status_queue = create_component_with_status_queue({
        'name': 'comp-xy',
        'args': [sys.executable, '-c', 'import time; time.sleep(0.001)'],
        'delay': 0,
        'revive': True,
        'start_delay': 0.001,
        'create_timeout': 2,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    assert component.status == Status.STOPPED
    assert (await status_queue.get() == Status.STARTING)
    assert (await status_queue.get() == Status.RUNNING)
    for _ in range(3):
        assert (await status_queue.get() == Status.STOPPING)
        assert (await status_queue.get() == Status.STOPPED)
        assert (await status_queue.get() == Status.STARTING)
        assert (await status_queue.get() == Status.RUNNING)
    assert status_queue.empty()
    await component.async_close()
    assert component.is_closed


async def test_revive_on_delay():
    component = Component({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(10)'],
        'delay': 1,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})
    for revive in [True, False] * 5:
        component.set_revive(revive)
        assert component.revive == revive
        assert component.status == Status.DELAYED
        await asyncio.sleep(0)
    await component.async_close()
    assert component.status == Status.STOPPED


async def test_stop_during_delay():
    component, status_queue = create_component_with_status_queue({
        'name': 'comp-xy',
        'args': [sys.executable, '-c', 'import time; time.sleep(10)'],
        'delay': 1,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    assert component.status == Status.DELAYED
    component.stop()
    assert (await status_queue.get() == Status.STOPPED)
    assert status_queue.empty()
    await component.async_close()
    assert component.is_closed


async def test_initial_status():
    component = Component({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(10)'],
        'delay': 1,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})
    assert component.status == Status.DELAYED
    await component.async_close()
    assert component.status == Status.STOPPED

    component = Component({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(10)'],
        'delay': 0,
        'revive': False})
    assert component.status == Status.STOPPED
    await component.async_close()
    assert component.status == Status.STOPPED


async def test_closed():
    component = Component({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(10)'],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})
    assert not component.is_closed
    await component.async_close()
    assert component.is_closed


async def test_conf_properties():
    conf = {'name': 'name',
            'args': [sys.executable, '-c', 'import time; time.sleep(10)'],
            'delay': 0,
            'revive': False,
            'start_delay': 0.001,
            'create_timeout': 0.1,
            'sigint_timeout': 0.001,
            'sigkill_timeout': 0.001}
    component = Component(conf)
    assert component.name == conf['name']
    assert component.delay == conf['delay']
    assert component.revive == conf['revive']
    await component.async_close()


@pytest.mark.timeout(1)
async def test_call_create_subprocess_exec_without_revive():
    with unittest.mock.patch('asyncio.create_subprocess_exec') as create:
        create.return_value.stdout.readline.return_value = None
        component = Component({
            'name': 'name',
            'args': [sys.executable, '-c', 'import time; time.sleep(0)'],
            'delay': 0,
            'revive': False,
            'start_delay': 0.001,
            'create_timeout': 0.1,
            'sigint_timeout': 0.001,
            'sigkill_timeout': 0.001})
        while create.call_count < 1:
            await asyncio.sleep(0.001)
        await component.async_close()


async def test_call_create_subprocess_exec_with_revive():
    with unittest.mock.patch('asyncio.create_subprocess_exec') as create:
        create.return_value.stdout.readline.return_value = None
        component = Component({
            'name': 'name',
            'args': [sys.executable, '-c', 'import time; time.sleep(0)'],
            'delay': 0,
            'revive': True,
            'start_delay': 0.001,
            'create_timeout': 0.1,
            'sigint_timeout': 0.001,
            'sigkill_timeout': 0.001})
        while create.call_count <= 5:
            await asyncio.sleep(0.001)
        await component.async_close()


async def test_process_stopped_on_close(process_queue):
    component = Component({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(10)'],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})
    p = await process_queue.get()
    await asyncio.sleep(0.01)
    assert p.returncode is None
    await component.async_close()
    assert p.returncode is not None


@pytest.mark.timeout(1)
async def test_process_stopped_on_stop(process_queue):
    component = Component({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(10)'],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})
    p = await process_queue.get()
    assert p.returncode is None
    component.stop()
    await asyncio.wait_for(p.wait(), 1)
    await component.async_close()


async def test_new_process_on_start(process_queue):
    component, status_queue = create_component_with_status_queue({
        'name': 'comp-xy',
        'args': [sys.executable, '-c', 'import time; time.sleep(100)'],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    for i in range(5):
        if i != 0:
            component.start()
        p = await process_queue.get()
        assert (await status_queue.get() == Status.STARTING)
        assert (await status_queue.get() == Status.RUNNING)
        assert p.returncode is None

        component.stop()
        assert (await status_queue.get() == Status.STOPPING)
        assert (await status_queue.get() == Status.STOPPED)
        assert p.returncode is not None

    await component.async_close()
    assert status_queue.empty()
    assert process_queue.empty()


async def test_soft_terminate_process(process_queue, tmpdir):
    component_path = tmpdir / 'component.py'
    running_path = tmpdir / 'running'
    signum = 'signal.SIGBREAK' if sys.platform == 'win32' else 'signal.SIGINT'
    with open(component_path, 'w', encoding='utf-8') as f:
        f.write('import signal, sys, time\n'
                f'signal.signal({signum}, lambda *args: sys.exit(123))\n'
                f'open(r"{running_path}", "w").close()\n'
                'while True:\n'
                '    time.sleep(0.001)\n')

    component = Component({
        'name': 'name',
        'args': [sys.executable, str(component_path)],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 1,
        'sigkill_timeout': 0.001})
    while not running_path.exists():
        await asyncio.sleep(0.001)

    p = await process_queue.get()
    assert p.returncode is None
    await component.async_close()
    assert p.returncode == 123


@pytest.mark.timeout(1)
async def test_hard_terminate_process(process_queue, tmpdir):
    component_path = tmpdir / 'component.py'
    running_path = tmpdir / 'running'
    signum = 'signal.SIGBREAK' if sys.platform == 'win32' else 'signal.SIGINT'
    with open(component_path, 'w', encoding='utf-8') as f:
        f.write('import signal, sys, time\n'
                f'signal.signal({signum}, lambda *args: None)\n'
                f'open(r"{running_path}", "w").close()\n'
                'while True:\n'
                '    time.sleep(0.001)\n')

    component = Component({
        'name': 'name',
        'args': [sys.executable, str(component_path)],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})
    while not running_path.exists():
        await asyncio.sleep(0.001)

    p = await process_queue.get()
    assert p.returncode is None
    await component.async_close()
    assert p.returncode is not None


async def test_noop_revive():
    component, status_queue = create_component_with_status_queue({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(30)'],
        'delay': 0,
        'revive': True,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    assert component.status == Status.STOPPED
    assert (await status_queue.get() == Status.STARTING)
    assert (await status_queue.get() == Status.RUNNING)

    component.set_revive(True)
    component.set_revive(True)
    component.set_revive(True)

    await asyncio.sleep(0.001)
    assert status_queue.empty()

    await component.async_close()


async def test_noop_start():
    component, status_queue = create_component_with_status_queue({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(30)'],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    while True:
        if await status_queue.get() == Status.RUNNING:
            break

    for _ in range(5):
        component.start()
    assert component.status == Status.RUNNING

    await asyncio.sleep(0.001)
    assert status_queue.empty()

    await component.async_close()


async def test_noop_stop():
    component, status_queue = create_component_with_status_queue({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(30)'],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    await status_queue.get() == Status.STARTING
    component.stop()
    while True:
        if await status_queue.get() == Status.STOPPED:
            break

    for _ in range(5):
        component.stop()
    assert component.status == Status.STOPPED

    await asyncio.sleep(0.001)
    assert status_queue.empty()

    await component.async_close()


async def test_starting_no_interrupt():
    component, status_queue = create_component_with_status_queue({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(30)'],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    assert component.status == Status.STOPPED
    assert (await status_queue.get() == Status.STARTING)

    for _ in range(5):
        component.start()
        component.stop()
    assert (await status_queue.get() == Status.RUNNING)
    assert (await status_queue.get() == Status.STOPPING)
    assert (await status_queue.get() == Status.STOPPED)

    await asyncio.sleep(0.001)
    assert status_queue.empty()

    await component.async_close()


async def test_stopping_no_interrupt():
    component, status_queue = create_component_with_status_queue({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(30)'],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    while True:
        if await status_queue.get() == Status.RUNNING:
            break
    component.stop()
    assert (await status_queue.get() == Status.STOPPING)

    for _ in range(5):
        component.stop()
        component.start()
    assert (await status_queue.get() == Status.STOPPED)
    assert (await status_queue.get() == Status.STARTING)
    assert (await status_queue.get() == Status.RUNNING)

    await asyncio.sleep(0.001)
    assert status_queue.empty()

    await component.async_close()


async def test_actions_not_queued_for_seq_exec():
    component, status_queue = create_component_with_status_queue({
        'name': 'name',
        'args': [sys.executable, '-c', 'import time; time.sleep(30)'],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})

    while True:
        if await status_queue.get() == Status.RUNNING:
            break

    for _ in range(5):
        component.start()
        component.stop()
    assert (await status_queue.get() == Status.STOPPING)
    assert (await status_queue.get() == Status.STOPPED)

    await asyncio.sleep(0.001)
    assert status_queue.empty()

    await component.async_close()


async def test_console_output(capsys):
    component, status_queue = create_component_with_status_queue({
        'name': 'name',
        'args': [sys.executable, '-c', 'print("abc")'],
        'delay': 0,
        'revive': False,
        'start_delay': 0.001,
        'create_timeout': 0.1,
        'sigint_timeout': 0.001,
        'sigkill_timeout': 0.001})
    while (await status_queue.get()) != Status.STOPPED:
        pass
    await component.async_close()

    captured = capsys.readouterr()
    assert captured.out.endswith('abc\n')
