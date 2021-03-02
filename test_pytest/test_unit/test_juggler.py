import asyncio
import collections
import contextlib
import itertools

import pytest

from hat import aio
from hat import json
from hat import juggler
from hat import util


pytestmark = pytest.mark.asyncio


@pytest.fixture
def server_port():
    return util.get_unused_udp_port()


@contextlib.asynccontextmanager
async def create_conn_pair(server_port, autoflush_delay):
    conn_queue = aio.Queue()
    srv = await juggler.listen('127.0.0.1', server_port, conn_queue.put_nowait,
                               autoflush_delay=autoflush_delay)
    conn = await juggler.connect(f'ws://127.0.0.1:{server_port}/ws',
                                 autoflush_delay=autoflush_delay)
    srv_conn = await conn_queue.get()
    try:
        yield conn, srv_conn
    finally:
        await conn.async_close()
        await srv.async_close()


@pytest.mark.parametrize("client_count", [1, 2, 5])
async def test_connect_listen(server_port, client_count):
    conn_queue = aio.Queue()
    address = f'ws://127.0.0.1:{server_port}/ws'

    with pytest.raises(Exception):
        await juggler.connect(address)

    srv = await juggler.listen('127.0.0.1', server_port, conn_queue.put_nowait)

    assert not srv.is_closed

    conns = collections.deque()

    for i in range(client_count):
        conn = await juggler.connect(address)
        srv_conn = await conn_queue.get()

        conns.append((conn, srv_conn))

    while conns:
        conn, srv_conn = conns.popleft()

        assert not conn.is_closed
        assert not srv_conn.is_closed

        await conn.async_close()

        assert conn.is_closed
        assert srv_conn.is_closed

    assert not srv.is_closed

    await srv.async_close()
    assert srv.is_closed

    with pytest.raises(Exception):
        await juggler.connect(address)


@pytest.mark.parametrize("client_count", [1, 2, 10])
async def test_srv_close_active_client(server_port, client_count):
    address = f'ws://127.0.0.1:{server_port}/ws'
    conn_closed_futures = []

    srv = await juggler.listen('127.0.0.1', server_port, lambda conn: None)

    for _ in range(client_count):
        conn = await juggler.connect(address)
        conn_closed_futures.append(conn.wait_closed())

    await asyncio.wait_for(srv.async_close(), 0.1)
    assert srv.is_closed

    await asyncio.wait_for(asyncio.gather(*conn_closed_futures), 0.1)


@pytest.mark.parametrize("data", [
    [True, False, True, False],
    [0, 1, 2, 3, 4, 5],
    [{}, {'a': 1}, {'a': 2}, {'a': 2, 'b': None}, {'b': None}],
    [0, False, '', [], {}, None]])
async def test_set_local_data(server_port, data):
    async with create_conn_pair(server_port, 0) as conn_pair:
        change_queues = []

        for conn in conn_pair:
            assert conn.local_data is None
            assert conn.remote_data is None
            change_queue = aio.Queue()
            conn.register_change_cb(lambda: change_queue.put_nowait(None))
            change_queues.append(change_queue)

        for i in data:
            for local, remote in itertools.permutations(zip(conn_pair,
                                                            change_queues)):
                local_conn, _ = local
                remote_conn, change_queue = remote

                local_conn.set_local_data(i)
                assert local_conn.local_data == i

                await change_queue.get()
                assert json.equals(remote_conn.remote_data,
                                   local_conn.local_data)


async def test_flush_local_data(server_port):
    async with create_conn_pair(server_port, 100) as conn_pair:
        local_conn, remote_conn = conn_pair
        change_queue = aio.Queue()
        remote_conn.register_change_cb(lambda: change_queue.put_nowait(None))

        local_conn.set_local_data([1])
        await asyncio.sleep(0.1)
        assert change_queue.empty()
        assert remote_conn.remote_data is None

        local_conn.set_local_data([1, 2])
        await asyncio.sleep(0.1)
        assert change_queue.empty()
        assert remote_conn.remote_data is None

        await local_conn.flush_local_data()
        await asyncio.wait_for(change_queue.get(), 0.1)
        assert json.equals(remote_conn.remote_data, local_conn.local_data)


@pytest.mark.parametrize("messages", [
    [False, False, True, False],
    [0, 0, 1, 2, 0, 3],
    [{}, {'a': 1}, {'a': 2}, {'a': 2, 'b': None}, {'b': None}],
    [0, 0.0, False, '', [], {}, None]])
async def test_send_receive(server_port, messages):
    async with create_conn_pair(server_port, 0.01) as conn_pair:
        for send_msg in messages:
            for local_conn, remote_conn in itertools.permutations(conn_pair):
                await local_conn.send(send_msg)
                rcv_msg = await remote_conn.receive()
                assert json.equals(send_msg, rcv_msg)


async def test_big_message_server_to_client(server_port):
    async with create_conn_pair(server_port, 0.01) as conn_pair:
        client_conn, server_conn = conn_pair
        big_msg = '1' * 4194304 * 2
        await server_conn.send(big_msg)
        assert big_msg == await client_conn.receive()


async def test_connection_closed(server_port):
    async with create_conn_pair(server_port, 0.01) as conn_pair:
        local_conn, remote_conn = conn_pair

        await remote_conn.async_close()

        with pytest.raises(ConnectionError):
            await local_conn.send([])
        with pytest.raises(ConnectionError):
            await local_conn.receive()
        with pytest.raises(ConnectionError):
            local_conn.set_local_data([])
        with pytest.raises(ConnectionError):
            await local_conn.flush_local_data()


async def test_autoflush_zero(server_port):
    async with create_conn_pair(server_port, 0) as conn_pair:
        conn1, conn2 = conn_pair
        assert conn1.local_data is None
        assert conn1.remote_data is None
        assert conn2.local_data is None
        assert conn2.remote_data is None

        conn1_changes = aio.Queue()
        conn2_changes = aio.Queue()
        conn1.register_change_cb(
            lambda: conn1_changes.put_nowait(conn1.remote_data))
        conn2.register_change_cb(
            lambda: conn2_changes.put_nowait(conn2.remote_data))

        conn1.set_local_data(123)
        conn1.set_local_data('abc')
        conn1.set_local_data('xyz')
        conn2.remote_data is None
        change1 = await conn2_changes.get()
        change2 = await conn2_changes.get()
        change3 = await conn2_changes.get()
        assert change1 == 123
        assert change2 == 'abc'
        assert change3 == 'xyz'
        assert conn2.remote_data == 'xyz'
        assert conn2_changes.empty()


async def test_autoflush_not_zero(server_port):
    async with create_conn_pair(server_port, 0.001) as conn_pair:
        conn1, conn2 = conn_pair
        assert conn1.local_data is None
        assert conn1.remote_data is None
        assert conn2.local_data is None
        assert conn2.remote_data is None

        conn1_changes = aio.Queue()
        conn2_changes = aio.Queue()
        conn1.register_change_cb(
            lambda: conn1_changes.put_nowait(conn1.remote_data))
        conn2.register_change_cb(
            lambda: conn2_changes.put_nowait(conn2.remote_data))

        conn1.set_local_data(123)
        conn1.set_local_data('abc')
        conn1.set_local_data('xyz')
        conn2.remote_data is None
        change = await conn2_changes.get()
        assert change == 'xyz'
        assert conn2.remote_data == 'xyz'
        assert conn2_changes.empty()


async def test_rpc(server_port):
    async with create_conn_pair(server_port, 0.001) as conn_pair:
        conn1, conn2 = conn_pair
        actions = {'act': lambda x: x + 1}
        rpc1 = juggler.RpcConnection(conn1, actions)
        rpc2 = juggler.RpcConnection(conn2, actions)

        result = await rpc1.call('act', 123)
        assert result == 124

        result = await rpc2.call('act', 321)
        assert result == 322

        with pytest.raises(Exception):
            await rpc1.call('act', '123')

        with pytest.raises(Exception):
            await rpc1.call('not act', 321)


async def test_example_docs():

    from hat import aio
    from hat import juggler
    from hat import util

    port = util.get_unused_tcp_port()
    host = '127.0.0.1'

    server_conns = aio.Queue()
    server = await juggler.listen(host, port, server_conns.put_nowait,
                                  autoflush_delay=0)

    client_conn = await juggler.connect(f'ws://{host}:{port}/ws',
                                        autoflush_delay=0)
    server_conn = await server_conns.get()

    server_remote_data = aio.Queue()
    server_conn.register_change_cb(
        lambda: server_remote_data.put_nowait(server_conn.remote_data))

    client_conn.set_local_data(123)
    data = await server_remote_data.get()
    assert data == 123

    await server.async_close()
    await client_conn.wait_closed()
    await server_conn.wait_closed()
