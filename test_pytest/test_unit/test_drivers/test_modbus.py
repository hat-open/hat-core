import asyncio
import subprocess
import time
import atexit
import contextlib
import enum
import sys

import pytest

from hat import aio
from hat import util
from hat.drivers import modbus
from hat.drivers import tcp


pytestmark = pytest.mark.asyncio


CommType = enum.Enum('CommType', ['TCP', 'SERIAL'])


if sys.platform == 'win32':
    comm_types = [CommType.TCP]
else:
    comm_types = [CommType.TCP, CommType.SERIAL]


@pytest.fixture
def tcp_addr():
    return tcp.Address('127.0.0.1', util.get_unused_tcp_port())


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
    return str(path1), str(path2), p


@pytest.fixture
async def create_master_slave(tcp_addr, nullmodem):

    @contextlib.asynccontextmanager
    async def create_master_slave(modbus_type, comm_type, read_cb=None,
                                  write_cb=None, write_mask_cb=None):
        if comm_type == CommType.TCP:
            slave_queue = aio.Queue()
            srv = await modbus.create_tcp_server(
                modbus_type, tcp_addr, slave_queue.put_nowait,
                read_cb, write_cb, write_mask_cb)
            master = await modbus.create_tcp_master(
                modbus_type, tcp_addr)
            slave = await slave_queue.get()
            try:
                yield master, slave
            finally:
                await master.async_close()
                await srv.async_close()

        elif comm_type == CommType.SERIAL:
            master = await modbus.create_serial_master(
                modbus_type, nullmodem[0])
            slave = await modbus.create_serial_slave(
                modbus_type, nullmodem[1], read_cb, write_cb, write_mask_cb)
            try:
                yield master, slave
            finally:
                await master.async_close()
                await slave.async_close()

        else:
            raise ValueError()

    return create_master_slave


@pytest.mark.parametrize("modbus_type", list(modbus.ModbusType))
async def test_create_tcp(tcp_addr, modbus_type):
    with pytest.raises(Exception):
        await modbus.create_tcp_master(modbus_type, tcp_addr)

    slave_queue = aio.Queue()
    srv = await modbus.create_tcp_server(modbus_type, tcp_addr,
                                         slave_queue.put_nowait)
    assert not srv.is_closed
    assert slave_queue.empty()

    masters = []
    slaves = []

    for _ in range(10):
        master = await modbus.create_tcp_master(modbus_type, tcp_addr)
        assert not master.is_closed
        masters.append(master)

        slave = await asyncio.wait_for(slave_queue.get(), 0.1)
        assert not slave.is_closed
        slaves.append(slave)

    for master, slave in zip(masters, slaves):
        assert not master.is_closed
        assert not slave.is_closed

        await master.async_close()
        assert master.is_closed
        await asyncio.wait_for(slave.wait_closed(), 0.1)

    masters = []
    slaves = []

    for _ in range(10):
        master = await modbus.create_tcp_master(modbus_type, tcp_addr)
        assert not master.is_closed
        masters.append(master)

        slave = await asyncio.wait_for(slave_queue.get(), 0.1)
        assert not slave.is_closed
        slaves.append(slave)

    await srv.async_close()

    for master, slave in zip(masters, slaves):
        await asyncio.wait_for(slave.wait_closed(), 0.1)
        await master.async_close()


@pytest.mark.skipif(sys.platform == 'win32', reason="can't simulate serial")
@pytest.mark.parametrize("modbus_type", list(modbus.ModbusType))
async def test_create_serial(nullmodem, modbus_type):
    master = await modbus.create_serial_master(modbus_type, nullmodem[0])
    slave = await modbus.create_serial_slave(modbus_type, nullmodem[1])
    assert not master.is_closed
    assert not slave.is_closed
    await master.async_close()
    await slave.async_close()


@pytest.mark.parametrize("modbus_type", list(modbus.ModbusType))
@pytest.mark.parametrize("comm_type", comm_types)
@pytest.mark.parametrize(
    "device_id, data_type, start_address, quantity, result", [
        (1, modbus.DataType.COIL, 1, 1, [0]),
        (2, modbus.DataType.COIL, 1, 1, [1]),
        (3, modbus.DataType.COIL, 3, 4, [1, 0, 1, 0]),
        (4, modbus.DataType.DISCRETE_INPUT, 1, 1, [0]),
        (5, modbus.DataType.DISCRETE_INPUT, 1, 2, [1, 0]),
        (6, modbus.DataType.HOLDING_REGISTER, 1, 1, [0]),
        (7, modbus.DataType.HOLDING_REGISTER, 1, 4, [1, 255, 1234, 0xFFFF]),
        (8, modbus.DataType.INPUT_REGISTER, 1, 1, [0]),
        (9, modbus.DataType.INPUT_REGISTER, 1, 4, [1, 255, 1234, 0xFFFF]),
        (1, modbus.DataType.INPUT_REGISTER, 1, 4, [1, 255, 1234, 0xFFFF]),
        (1, modbus.DataType.QUEUE, 123, None, [1, 255, 1234, 0xFFFF]),
        (1, modbus.DataType.COIL, 1, 1, modbus.Error.INVALID_FUNCTION_CODE),
        (1, modbus.DataType.COIL, 1, 3, modbus.Error.INVALID_DATA_ADDRESS),
        (1, modbus.DataType.COIL, 1, 1, modbus.Error.INVALID_DATA_VALUE),
        (1, modbus.DataType.COIL, 1, 3, modbus.Error.FUNCTION_ERROR)
    ])
async def test_read(create_master_slave, modbus_type, comm_type,
                    device_id, data_type, start_address, quantity, result):
    read_queue = aio.Queue()

    async def on_read(slave, device_id, data_type, start_address, quantity):
        f = asyncio.Future()
        entry = device_id, data_type, start_address, quantity, f
        read_queue.put_nowait(entry)
        return await f

    async with create_master_slave(modbus_type, comm_type,
                                   read_cb=on_read) as (master, slave):

        read_future = asyncio.ensure_future(master.read(
            device_id, data_type, start_address, quantity))

        entry = await read_queue.get()
        assert entry[0] == device_id
        assert entry[1] == data_type
        assert entry[2] == start_address
        assert entry[3] == quantity
        entry[4].set_result(result)

        read_result = await read_future
        assert read_result == result


@pytest.mark.parametrize("modbus_type", list(modbus.ModbusType))
@pytest.mark.parametrize("comm_type", comm_types)
@pytest.mark.parametrize(
    "device_id, data_type, start_address, values, result", [
        (1, modbus.DataType.COIL, 1, [0], None),
        (2, modbus.DataType.COIL, 1, [1], None),
        (3, modbus.DataType.COIL, 3, [1, 0, 1, 0], None),
        (6, modbus.DataType.HOLDING_REGISTER, 1, [0], None),
        (7, modbus.DataType.HOLDING_REGISTER, 1, [1, 255, 1234, 0xFFFF], None),
        (1, modbus.DataType.COIL, 1, [0], modbus.Error.INVALID_FUNCTION_CODE),
        (1, modbus.DataType.COIL, 1, [0], modbus.Error.INVALID_DATA_ADDRESS),
        (1, modbus.DataType.COIL, 1, [0], modbus.Error.INVALID_DATA_VALUE),
        (1, modbus.DataType.COIL, 1, [0], modbus.Error.FUNCTION_ERROR)
    ])
async def test_write(create_master_slave, modbus_type, comm_type,
                     device_id, data_type, start_address, values, result):
    write_queue = aio.Queue()

    async def on_write(slave, device_id, data_type, start_address, values):
        f = asyncio.Future()
        entry = device_id, data_type, start_address, values, f
        write_queue.put_nowait(entry)
        return await f

    async with create_master_slave(modbus_type, comm_type,
                                   write_cb=on_write) as (master, slave):

        write_future = asyncio.ensure_future(master.write(
            device_id, data_type, start_address, values))

        entry = await write_queue.get()
        assert entry[0] == device_id
        assert entry[1] == data_type
        assert entry[2] == start_address
        assert entry[3] == values
        entry[4].set_result(result)

        read_result = await write_future
        assert read_result == result
