import asyncio
import atexit
import subprocess
import sys
import time

import pytest

import hat.drivers.serial


pytestmark = [pytest.mark.asyncio,
              pytest.mark.skipif(sys.platform == 'win32',
                                 reason="can't simulate serial")]


@pytest.fixture
def nullmodem(request, tmp_path):
    path1 = tmp_path / '1'
    path2 = tmp_path / '2'
    p = subprocess.Popen(
        ['socat',
         f'pty,link={path1},raw,echo=0',
         f'pty,link={path2},raw,echo=0'])
    while not path1.exists() or not path2.exists():
        time.sleep(0.001)

    def finalizer():
        p.terminate()

    atexit.register(finalizer)
    request.addfinalizer(finalizer)
    return path1, path2, p


async def test_create(nullmodem):
    conn = await hat.drivers.serial.create(port=str(nullmodem[0]),
                                           rtscts=True,
                                           dsrdtr=True)
    assert not conn.is_closed
    await conn.async_close()
    assert conn.is_closed


async def test_read_write(nullmodem):
    conn1 = await hat.drivers.serial.create(port=str(nullmodem[0]),
                                            rtscts=True,
                                            dsrdtr=True)
    conn2 = await hat.drivers.serial.create(port=str(nullmodem[1]),
                                            rtscts=True,
                                            dsrdtr=True)

    data = b'test1'
    await conn1.write(data)
    assert data == await conn2.read(len(data))

    data = b'test2'
    await conn2.write(data)
    assert data == await conn1.read(len(data))

    await conn1.async_close()
    await conn2.async_close()

    with pytest.raises(ConnectionError):
        await conn1.read(1)

    with pytest.raises(ConnectionError):
        await conn2.write(b'')


async def test_close_while_reading(nullmodem):
    conn = await hat.drivers.serial.create(port=str(nullmodem[0]),
                                           rtscts=True,
                                           dsrdtr=True)

    read_future = asyncio.ensure_future(conn.read(1))

    await conn.async_close()

    with pytest.raises(ConnectionError):
        read_future.result()


async def test_close_nullmodem(nullmodem):
    conn = await hat.drivers.serial.create(port=str(nullmodem[0]),
                                           rtscts=True,
                                           dsrdtr=True)

    read_future = asyncio.ensure_future(conn.read(1))
    write_future = asyncio.ensure_future(conn.write(b'123'))

    nullmodem[2].terminate()

    with pytest.raises(ConnectionError):
        await read_future

    with pytest.raises(ConnectionError):
        await write_future

    await conn.async_close()
