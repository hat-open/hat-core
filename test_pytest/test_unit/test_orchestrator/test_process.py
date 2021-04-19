import asyncio
import collections
import sys

import pytest

import hat.orchestrator.process


pytestmark = pytest.mark.asyncio


async def test_create_process():
    process = await hat.orchestrator.process.create_process([
        sys.executable, '-c', 'import time; time.sleep(10)'])

    assert process.is_open
    assert process.returncode is None

    await process.async_close()

    assert process.is_closed
    assert process.returncode is not None


@pytest.mark.parametrize("proc_count", [1, 2, 5])
async def test_pid(proc_count):
    processes = collections.deque()
    pids = set()

    for i in range(proc_count):
        process = await hat.orchestrator.process.create_process([
            sys.executable, '-c', 'import time; time.sleep(10)'])
        pid = process.pid

        assert pid
        assert pid not in pids

        processes.append(process)
        pids.add(pid)

    while processes:
        process = processes.pop()
        await process.async_close()


async def test_returncode():
    process = await hat.orchestrator.process.create_process([
        sys.executable, '-c', 'import time; time.sleep(0)'])
    await process.wait_closed()
    assert process.returncode == 0

    process = await hat.orchestrator.process.create_process([
        sys.executable, '-c', 'import time; time.sleep(10)'])
    await process.async_close()
    assert process.returncode


async def test_readline():
    process = await hat.orchestrator.process.create_process([
        sys.executable, '-c', 'print("a"); print("b"); print("c", end="")'])

    line = await process.readline()
    assert line == 'a'

    line = await process.readline()
    assert line == 'b'

    line = await process.readline()
    assert line == 'c'

    with pytest.raises(ConnectionError):
        await process.readline()

    await process.wait_closed()


@pytest.mark.skip(reason="closed stdout not detected")
async def test_close_stdout():
    process = await hat.orchestrator.process.create_process([
        sys.executable, '-c',
        'print(123); '
        'import sys; sys.stdout.close(); '
        'import time; time.sleep(10)'])

    line = await process.readline()
    assert line == '123'

    with pytest.raises(ConnectionError):
        await process.readline()

    assert process.is_open

    await process.async_close()


async def test_sigint(tmpdir):
    script_path = tmpdir / 'script.py'
    running_path = tmpdir / 'running'
    signum = 'signal.SIGBREAK' if sys.platform == 'win32' else 'signal.SIGINT'
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write('import signal, sys, time\n'
                f'signal.signal({signum}, lambda *args: sys.exit(123))\n'
                f'open(r"{running_path}", "w").close()\n'
                'while True:\n'
                '    time.sleep(0.001)\n')

    args = [sys.executable, str(script_path)]
    process = await hat.orchestrator.process.create_process(args)

    while not running_path.exists():
        await asyncio.sleep(0.001)

    assert process.returncode is None

    await process.async_close()

    assert process.returncode == 123


async def test_sigkill(tmpdir):
    script_path = tmpdir / 'script.py'
    running_path = tmpdir / 'running'
    signum = 'signal.SIGBREAK' if sys.platform == 'win32' else 'signal.SIGINT'
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write('import signal, sys, time\n'
                f'signal.signal({signum}, lambda *args: None)\n'
                f'open(r"{running_path}", "w").close()\n'
                'while True:\n'
                '    time.sleep(0.001)\n')

    args = [sys.executable, str(script_path)]
    process = await hat.orchestrator.process.create_process(
        args, sigint_timeout=0.001)

    while not running_path.exists():
        await asyncio.sleep(0.001)

    assert process.returncode is None

    await process.async_close()

    assert process.returncode


@pytest.mark.skipif(sys.platform != 'win32', reason="only for win32")
async def test_win32_job():
    job = hat.orchestrator.process.Win32Job()
    process = await hat.orchestrator.process.create_process([
        sys.executable, '-c', 'import time; time.sleep(10)'])
    job.add_process(process)

    await job.async_close()
    await asyncio.wait_for(process.wait_closed(), 1)
