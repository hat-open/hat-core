"""Asyncio wrapper for serial communication

.. warning::

    implementation is based on read with timeout for periodical checking
    if connection is closed by user - better way of canceling active read
    operation is needed

Attributes:
    mlog (logging.Logger): module logger

"""

import asyncio
import functools
import logging

import serial

from hat.util import aio


mlog = logging.getLogger(__name__)


async def open(conf):
    """Open serial port

    Args:
        conf (hat.json.Data): configuration defined by
            'hat://drivers/serial.yaml#'

    Returns:
        Connection

    """
    executor = aio.create_executor()
    s = await executor(functools.partial(
            serial.Serial,
            port=conf['port'],
            baudrate=conf.get('baudrate', 9600),
            bytesize=getattr(serial, conf.get('bytesize', 'EIGHTBITS')),
            parity=getattr(serial, conf.get('parity', 'PARITY_NONE')),
            stopbits=getattr(serial, conf.get('stopbits', 'STOPBITS_ONE')),
            rtscts=conf.get('rtscts', False),
            dsrdtr=conf.get('dsrdtr', False),
            timeout=1))

    read_queue = aio.Queue()
    write_queue = aio.Queue()
    async_group = aio.Group()
    async_group.spawn(_action_loop, async_group, executor, read_queue, 0)
    async_group.spawn(_action_loop, async_group, executor, write_queue,
                      conf.get('silent_interval', 0))
    async_group.spawn(aio.call_on_cancel, executor, _ext_close, s)

    conn = Connection()
    conn._s = s
    conn._read_queue = read_queue
    conn._write_queue = write_queue
    conn._async_group = async_group
    return conn


class Connection:
    """Serial connection

    For creating new instances see :func:`hat.drivers.serial.open`

    """

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    async def read(self, size):
        """Read

        Args:
            size (int): number of bytes to read

        Returns:
            bytes

        """
        result = asyncio.Future()
        await self._read_queue.put(([_ext_read, self._s, size], result))
        return await result

    async def write(self, data):
        """Write

        Args:
            data (bytes): data

        """
        result = asyncio.Future()
        await self._write_queue.put(([_ext_write, self._s, data], result))
        await result


async def _action_loop(async_group, executor, queue, delay):
    result = None
    try:
        while True:
            await asyncio.sleep(delay)
            args, result = await queue.get()
            data = await async_group.spawn(executor, *args)
            result.set_result(data)
            result = None
    except asyncio.CancelledError:
        pass
    except Exception as e:
        if result:
            result.set_exception(e)
            result = None
    finally:
        async_group.close()
        queue.close()
        if result:
            result.set_exception(EOFError())
        while not queue.empty():
            _, result = queue.get_nowait()
            result.set_exception(EOFError())


def _ext_read(s, size):
    buff = b''
    while True:
        try:
            buff += s.read(size - len(buff))
        except Exception as e:
            raise EOFError() from e
        if len(buff) >= size:
            return buff


def _ext_write(s, data):
    s.write(data)
    s.flush()


def _ext_close(s):
    s.close()
