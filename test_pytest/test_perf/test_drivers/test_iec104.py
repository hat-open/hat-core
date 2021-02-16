import asyncio
import datetime

import pytest

from hat import aio
from hat import util
from hat.drivers import iec104


pytestmark = pytest.mark.asyncio


@pytest.fixture
def addr():
    return iec104.Address('127.0.0.1', util.get_unused_tcp_port())


@pytest.mark.parametrize("window_size", [1, 10, 100])
@pytest.mark.parametrize("data_count", [1, 100, 10000])
async def test_data_sequence(duration, addr, window_size, data_count):

    data = iec104.Data(value=iec104.DoubleValue.ON,
                       quality=iec104.Quality(invalid=False,
                                              not_topical=False,
                                              substituted=False,
                                              blocked=False,
                                              overflow=None),
                       time=iec104.time_from_datetime(datetime.datetime.now()),
                       asdu_address=123,
                       io_address=321,
                       cause=iec104.Cause.SPONTANEOUS,
                       is_test=False)

    conn2_future = asyncio.Future()
    srv = await iec104.listen(conn2_future.set_result, addr,
                              send_window_size=window_size + 1,
                              receive_window_size=window_size - 1)
    conn1 = await iec104.connect(addr,
                                 send_window_size=window_size + 1,
                                 receive_window_size=window_size - 1)
    conn2 = await conn2_future

    with duration(f'data count: {data_count}; window_size: {window_size}'):
        for _ in range(data_count):
            conn1.notify_data_change([data])
            await conn2.receive()

    await conn1.async_close()
    await conn2.async_close()
    await srv.async_close()


@pytest.mark.parametrize("window_size", [1, 10, 100])
@pytest.mark.parametrize("data_count", [1, 100, 10000])
async def test_data_paralel(duration, addr, window_size, data_count):

    data = iec104.Data(value=iec104.DoubleValue.ON,
                       quality=iec104.Quality(invalid=False,
                                              not_topical=False,
                                              substituted=False,
                                              blocked=False,
                                              overflow=None),
                       time=iec104.time_from_datetime(datetime.datetime.now()),
                       asdu_address=123,
                       io_address=321,
                       cause=iec104.Cause.SPONTANEOUS,
                       is_test=False)

    conn2_future = asyncio.Future()
    srv = await iec104.listen(conn2_future.set_result, addr,
                              send_window_size=window_size + 1,
                              receive_window_size=window_size - 1)
    conn1 = await iec104.connect(addr,
                                 send_window_size=window_size + 1,
                                 receive_window_size=window_size - 1)
    conn2 = await conn2_future

    async def producer(conn):
        for _ in range(data_count):
            conn.notify_data_change([data])

    async def consumer(conn):
        for _ in range(data_count):
            await conn.receive()

    async_group = aio.Group()
    with duration(f'data count: {data_count}; window_size: {window_size}'):
        async_group.spawn(producer, conn1)
        async_group.spawn(consumer, conn2)
        await async_group.async_close(cancel=False)

    await conn1.async_close()
    await conn2.async_close()
    await srv.async_close()
