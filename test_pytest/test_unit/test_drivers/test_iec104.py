import asyncio
import datetime
import math

import pytest

from hat import aio
from hat.drivers import iec104


pytestmark = pytest.mark.asyncio


async def test_server_without_connections(unused_tcp_port):
    srv = await iec104.listen(connection_cb=lambda _: None,
                              host='127.0.0.1',
                              port=unused_tcp_port)
    assert not srv.is_closed
    assert len(srv.addresses) == 1
    addr = srv.addresses[0]
    assert addr.host == '127.0.0.1'
    assert addr.port == unused_tcp_port

    await srv.async_close()
    assert srv.is_closed


async def test_connect(unused_tcp_port):
    conn_queue = aio.Queue()
    srv = await iec104.listen(connection_cb=conn_queue.put_nowait,
                              host='127.0.0.1',
                              port=unused_tcp_port)
    conn = await iec104.connect(host='127.0.0.1',
                                port=unused_tcp_port)

    srv_conn = await asyncio.wait_for(conn_queue.get(), 0.1)

    assert conn.info.local_addr == srv_conn.info.remote_addr
    assert conn.info.remote_addr == srv_conn.info.local_addr
    assert conn.info.local_addr != conn.info.remote_addr
    assert conn.info.remote_addr == srv.addresses[0]

    assert not srv.is_closed
    assert not conn.is_closed
    assert not srv_conn.is_closed

    await srv.async_close()
    await asyncio.wait_for(srv_conn.wait_closed(), 0.1)
    await asyncio.wait_for(conn.wait_closed(), 0.1)


@pytest.mark.parametrize("conn_count", [1, 2, 10])
async def test_multiple_connections(unused_tcp_port, conn_count):
    conn_queue = aio.Queue()
    srv = await iec104.listen(connection_cb=conn_queue.put_nowait,
                              host='127.0.0.1',
                              port=unused_tcp_port)

    conns = []
    for _ in range(conn_count):
        conn = await iec104.connect(host='127.0.0.1',
                                    port=unused_tcp_port)
        conns.append(conn)

    srv_conns = []
    for _ in range(conn_count):
        srv_conn = await asyncio.wait_for(conn_queue.get(), 0.1)
        srv_conns.append(srv_conn)

    for conn in conns:
        await conn.async_close()
    for srv_conn in srv_conns:
        await srv_conn.wait_closed()
    await srv.async_close()


async def test_interogate(unused_tcp_port):
    conn_queue = aio.Queue()
    interrogate_queue = aio.Queue()

    async def on_interrogate(conn, asdu):
        f = asyncio.Future()
        interrogate_queue.put_nowait((asdu, f))
        result = await f
        return result

    srv = await iec104.listen(connection_cb=conn_queue.put_nowait,
                              host='127.0.0.1',
                              port=unused_tcp_port,
                              interrogate_cb=on_interrogate)
    conn = await iec104.connect(host='127.0.0.1',
                                port=unused_tcp_port)
    srv_conn = await conn_queue.get()

    conn_f = asyncio.ensure_future(conn.interrogate(123))
    asdu, srv_conn_f = await asyncio.wait_for(interrogate_queue.get(), 0.1)
    assert asdu == 123
    data = iec104.Data(
        value=iec104.SingleValue.ON,
        quality=iec104.Quality(
            invalid=False,
            not_topical=False,
            substituted=False,
            blocked=False,
            overflow=False),
        time=None,
        asdu_address=asdu,
        io_address=1,
        cause=iec104.Cause.INTERROGATED_STATION,
        is_test=False)
    srv_conn_f.set_result([data])
    result = await conn_f
    assert result == [data]

    await srv.async_close()
    await conn.async_close()
    await srv_conn.async_close()


async def test_counter_interogate(unused_tcp_port):
    conn_queue = aio.Queue()
    counter_interrogate_queue = aio.Queue()

    async def on_counter_interrogate(conn, asdu, freeze):
        f = asyncio.Future()
        counter_interrogate_queue.put_nowait((asdu, freeze, f))
        result = await f
        return result

    srv = await iec104.listen(connection_cb=conn_queue.put_nowait,
                              host='127.0.0.1',
                              port=unused_tcp_port,
                              counter_interrogate_cb=on_counter_interrogate)
    conn = await iec104.connect(host='127.0.0.1',
                                port=unused_tcp_port)
    srv_conn = await conn_queue.get()

    conn_f = asyncio.ensure_future(conn.counter_interrogate(123))
    asdu, freeze, srv_conn_f = await asyncio.wait_for(
        counter_interrogate_queue.get(), 0.1)
    assert asdu == 123
    assert freeze == iec104.FreezeCode.READ
    data = iec104.Data(
        value=iec104.BinaryCounterValue(
            value=321,
            sequence=1,
            overflow=False,
            adjusted=False,
            invalid=False),
        quality=None,
        time=None,
        asdu_address=asdu,
        io_address=1,
        cause=iec104.Cause.INTERROGATED_COUNTER,
        is_test=False)
    srv_conn_f.set_result([data])
    result = await conn_f
    assert result == [data]

    await srv.async_close()
    await conn.async_close()
    await srv_conn.async_close()


@pytest.mark.parametrize("data", [
    iec104.Data(value=iec104.SingleValue.ON,
                quality=iec104.Quality(invalid=False,
                                       not_topical=False,
                                       substituted=False,
                                       blocked=False,
                                       overflow=False),
                time=None,
                asdu_address=123,
                io_address=321,
                cause=iec104.Cause.SPONTANEOUS,
                is_test=False),
    iec104.Data(value=iec104.DoubleValue.FAULT,
                quality=iec104.Quality(invalid=True,
                                       not_topical=False,
                                       substituted=True,
                                       blocked=False,
                                       overflow=False),
                time=iec104.time_from_datetime(datetime.datetime.now()),
                asdu_address=1,
                io_address=2,
                cause=iec104.Cause.SPONTANEOUS,
                is_test=True),
    iec104.Data(value=iec104.StepPositionValue(value=32,
                                               transient=False),
                quality=iec104.Quality(invalid=False,
                                       not_topical=True,
                                       substituted=False,
                                       blocked=True,
                                       overflow=False),
                time=iec104.time_from_datetime(datetime.datetime.now(), False),
                asdu_address=1,
                io_address=2,
                cause=iec104.Cause.SPONTANEOUS,
                is_test=False),
    iec104.Data(value=iec104.BitstringValue(value=b'1234'),
                quality=iec104.Quality(invalid=False,
                                       not_topical=False,
                                       substituted=False,
                                       blocked=False,
                                       overflow=False),
                time=None,
                asdu_address=1,
                io_address=2,
                cause=iec104.Cause.SPONTANEOUS,
                is_test=False),
    iec104.Data(value=iec104.NormalizedValue(value=0.123),
                quality=None,
                time=None,
                asdu_address=1,
                io_address=2,
                cause=iec104.Cause.SPONTANEOUS,
                is_test=False),
    iec104.Data(value=iec104.ScaledValue(value=-123),
                quality=iec104.Quality(invalid=False,
                                       not_topical=False,
                                       substituted=False,
                                       blocked=False,
                                       overflow=True),
                time=None,
                asdu_address=1,
                io_address=2,
                cause=iec104.Cause.SPONTANEOUS,
                is_test=False),
    iec104.Data(value=iec104.FloatingValue(value=123.456),
                quality=iec104.Quality(invalid=False,
                                       not_topical=False,
                                       substituted=False,
                                       blocked=False,
                                       overflow=False),
                time=None,
                asdu_address=1,
                io_address=2,
                cause=iec104.Cause.SPONTANEOUS,
                is_test=False)
])
async def test_receive(unused_tcp_port, data):
    conn_queue = aio.Queue()
    srv = await iec104.listen(connection_cb=conn_queue.put_nowait,
                              host='127.0.0.1',
                              port=unused_tcp_port)
    conn = await iec104.connect(host='127.0.0.1',
                                port=unused_tcp_port)
    srv_conn = await conn_queue.get()

    srv_conn.notify_data_change([data])
    result = await conn.receive()
    if (isinstance(data.value, iec104.NormalizedValue) or
            isinstance(data.value, iec104.FloatingValue)):
        assert math.isclose(data.value.value, result[0].value.value,
                            rel_tol=1e-3)
        data = data._replace(
            value=data.value._replace(
                value=result[0].value.value))
    assert result == [data]

    await srv.async_close()
    await conn.async_close()
    await srv_conn.async_close()


@pytest.mark.parametrize("command", [
    iec104.Command(action=iec104.Action.EXECUTE,
                   value=iec104.SingleValue.OFF,
                   asdu_address=1,
                   io_address=2,
                   time=None,
                   qualifier=1),
    iec104.Command(action=iec104.Action.CANCEL,
                   value=iec104.DoubleValue.ON,
                   asdu_address=2,
                   io_address=1,
                   time=iec104.time_from_datetime(datetime.datetime.now()),
                   qualifier=2),
    iec104.Command(action=iec104.Action.SELECT,
                   value=iec104.RegulatingValue.HIGHER,
                   asdu_address=1,
                   io_address=2,
                   time=None,
                   qualifier=3),
    iec104.Command(action=iec104.Action.CANCEL,
                   value=iec104.NormalizedValue(value=0.321),
                   asdu_address=1,
                   io_address=2,
                   time=None,
                   qualifier=4),
    iec104.Command(action=iec104.Action.EXECUTE,
                   value=iec104.ScaledValue(value=123),
                   asdu_address=1,
                   io_address=2,
                   time=None,
                   qualifier=5),
    iec104.Command(action=iec104.Action.EXECUTE,
                   value=iec104.FloatingValue(value=-123.456),
                   asdu_address=1,
                   io_address=2,
                   time=None,
                   qualifier=6)
])
@pytest.mark.parametrize("success", [True, False])
async def test_send_command(unused_tcp_port, command, success):
    conn_queue = aio.Queue()

    async def on_command(conn, commands):
        nonlocal command
        if (isinstance(command.value, iec104.NormalizedValue) or
                isinstance(command.value, iec104.FloatingValue)):
            assert math.isclose(command.value.value, commands[0].value.value,
                                rel_tol=1e-3)
            command = command._replace(
                value=command.value._replace(
                    value=commands[0].value.value))
        assert commands == [command]
        return success

    srv = await iec104.listen(connection_cb=conn_queue.put_nowait,
                              host='127.0.0.1',
                              port=unused_tcp_port,
                              command_cb=on_command)
    conn = await iec104.connect(host='127.0.0.1',
                                port=unused_tcp_port)
    srv_conn = await conn_queue.get()

    result = await conn.send_command(command)
    assert result == success

    await srv.async_close()
    await conn.async_close()
    await srv_conn.async_close()
