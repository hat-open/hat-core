"""Asyncio wrapper for serial communication

.. warning::

    implementation is based on read with timeout for periodical checking
    if connection is closed by user - better way of canceling active read
    operation is needed

"""

import asyncio
import enum
import logging

import serial

from hat import aio


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


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


async def create(port: str, *,
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
    conn = Connection()
    conn._silent_interval = silent_interval
    conn._read_queue = aio.Queue()
    conn._write_queue = aio.Queue()
    conn._executor = aio.create_executor()

    conn._serial = await conn._executor(
        serial.Serial,
        port=port,
        baudrate=baudrate,
        bytesize=getattr(serial, bytesize.value),
        parity=getattr(serial, parity.value),
        stopbits=getattr(serial, stopbits.value),
        rtscts=rtscts,
        dsrdtr=dsrdtr,
        timeout=1)

    conn._async_group = aio.Group()
    conn._async_group.spawn(aio.call_on_cancel, conn._on_close)
    conn._async_group.spawn(conn._read_loop)
    conn._async_group.spawn(conn._write_loop)

    return conn


class Connection(aio.Resource):
    """Serial connection

    For creating new instances see `create` coroutine.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def read(self, size: int) -> bytes:
        """Read

        Args:
            size: number of bytes to read

        Raises:
            ConnectionError

        """
        result = asyncio.Future()
        try:
            self._read_queue.put_nowait((size, result))
        except aio.QueueClosedError:
            raise ConnectionError()
        return await result

    async def write(self, data: bytes):
        """Write

        Raises:
            ConnectionError

        """
        result = asyncio.Future()
        try:
            self._write_queue.put_nowait((data, result))
        except aio.QueueClosedError:
            raise ConnectionError()
        await result

    async def _on_close(self):
        await self._executor(self._serial.close)

    async def _read_loop(self):
        result = None
        try:
            async for size, result in self._read_queue:
                data = bytearray()
                while len(data) < size:
                    temp = await self._executor(self._serial.read,
                                                size - len(data))
                    data.extend(temp)
                result.set_result(bytes(data))

        except Exception as e:
            mlog.warning('read loop error: %s', e, exc_info=e)

        finally:
            self._async_group.close()
            _close_queue(self._read_queue)
            if result and not result.done():
                result.set_exception(ConnectionError())

    async def _write_loop(self):
        result = None
        try:
            async for data, result in self._write_queue:
                await self._executor(self._serial.write, data)
                await self._executor(self._serial.flush)
                result.set_result(None)
                await asyncio.sleep(self._silent_interval)

        except Exception as e:
            mlog.warning('read loop error: %s', e, exc_info=e)

        finally:
            self._async_group.close()
            _close_queue(self._write_queue)
            if result and not result.done():
                result.set_exception(ConnectionError())


def _close_queue(queue):
    queue.close()
    while not queue.empty():
        _, result = queue.get_nowait()
        result.set_exception(ConnectionError())
