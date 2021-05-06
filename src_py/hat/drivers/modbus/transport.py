"""Writer and Reader wrappers"""

import abc
import typing

from hat.drivers import serial
from hat.drivers import tcp


Data = typing.Union[bytes, bytearray, memoryview]


class Writer(abc.ABC):

    @abc.abstractmethod
    async def write(self, data: Data):
        pass


class TcpWriter(Writer):

    def __init__(self, conn: tcp.Connection):
        self._conn = conn

    async def write(self, data: Data):
        self._conn.write(data)
        await self._conn.drain()


class SerialWriter(Writer):

    def __init__(self, conn: serial.Connection):
        self._conn = conn

    async def write(self, data: Data):
        await self._conn.write(data)


class Reader(abc.ABC):

    @abc.abstractmethod
    async def read(self, size: int) -> Data:
        pass


class TcpReader(Reader):

    def __init__(self, conn: tcp.Connection):
        self._conn = conn

    async def read(self, size: int) -> Data:
        return await self._conn.readexactly(size)


class SerialReader(Reader):

    def __init__(self, conn: serial.Connection):
        self._conn = conn

    async def read(self, size: int) -> Data:
        return await self._conn.read(size)


class MemoryReader(Reader):

    def __init__(self, data: Data):
        self._data = memoryview(data)

    async def read(self, size: int) -> Data:
        if len(self._data) < size:
            raise Exception('insufficient data')
        data, self._data = self._data[:size], self._data[size:]
        return data


class CachingReader(Reader):

    def __init__(self, reader: Reader):
        self._reader = reader
        self._cache = bytearray()

    @property
    def cache(self) -> Data:
        return self._cache

    async def read(self, size: int) -> Data:
        data = await self._reader.read(size)
        self._cache.extend(data)
        return data
