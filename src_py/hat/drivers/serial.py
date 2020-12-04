"""Asyncio wrapper for serial communication

.. warning::

    implementation is based on read with timeout for periodical checking
    if connection is closed by user - better way of canceling active read
    operation is needed

Attributes:
    mlog (logging.Logger): module logger

"""

import asyncio
import enum
import functools
import logging

import serial

from hat import aio


mlog = logging.getLogger(__name__)


class ByteSize(enum.Enum):
    FIVEBITS = 'FIVEBITS'
    SIXBITS = 'SIXBITS'
    SEVENBITS = 'SEVENBITS'
    EIGHTBITS = 'EIGHTBITS'


class Parity(enum.Enum):
    NONE = 'PARITY_NONE'
    EVEN = 'PARITY_EVEN'
    ODD = 'PARITY_ODD'
    MARK = 'PARITI_MARK'
    SPACE = 'PARITY_SPACE'


class StopBits(enum.Enum):
    ONE = 'STOPBITS_ONE'
    ONE_POINT_FIVE = 'STOPBITS_ONE_POINT_FIVE'
    TWO = 'STOPBITS_TWO'


async def open(port: str, *,
               baudrate: int = 9600,
               bytesize: ByteSize = ByteSize.EIGHTBITS,
               parity: Parity = Parity.NONE,
               stopbits: StopBits = StopBits.ONE,
               rtscts: bool = False,
               dsrdtr: bool = False,
               silent_interval: float = 0
               ) -> 'Connection':
    """Open serial port

    Args:
        port: port name dependent of operating system
            (e.g. `/dev/ttyUSB0`, `COM3`, ...)
        baudrate: baud rate
        bytesize: number of data bits
        parity: parity checking
        stopbits: number of stop bits
        rtscts: enable hardware RTS/CTS flow control
        dsrdtr: enable hardware DSR/DTR flow control
        silent_interval: minimum time in seconds between writing two
            consecutive messages

    """
    executor = aio.create_executor()
    s = await executor(functools.partial(
            serial.Serial,
            port=port,
            baudrate=baudrate,
            bytesize=getattr(serial, bytesize.value),
            parity=getattr(serial, parity.value),
            stopbits=getattr(serial, stopbits.value),
            rtscts=rtscts,
            dsrdtr=dsrdtr,
            timeout=1))

    read_queue = aio.Queue()
    write_queue = aio.Queue()
    async_group = aio.Group()
    async_group.spawn(_action_loop, async_group, executor, read_queue, 0)
    async_group.spawn(_action_loop, async_group, executor, write_queue,
                      silent_interval)
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
