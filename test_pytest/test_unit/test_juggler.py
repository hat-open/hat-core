import collections
import itertools
import asyncio

import pytest

from hat.util import aio
from hat.util import json
from hat import juggler


@pytest.fixture
def short_sync_local_delay(monkeypatch):
    module = juggler
    monkeypatch.setattr(module, 'sync_local_delay', 0.001)


@pytest.fixture
def long_sync_local_delay(monkeypatch):
    module = juggler
    monkeypatch.setattr(module, 'sync_local_delay', 1_000_000)


@pytest.fixture
async def client_server_connection(unused_tcp_port_factory):
    address = create_address(unused_tcp_port_factory)
    srv_conn_future = asyncio.Future()
    srv = await juggler.listen(address,
                               lambda conn: srv_conn_future.set_result(conn))
    conn = await juggler.connect(address)
    srv_conn = await srv_conn_future
    yield conn, srv_conn
    await conn.async_close()
    await srv.async_close()


def create_address(unused_tcp_port_factory):
    return f'ws://127.0.0.1:{unused_tcp_port_factory()}/ws'


@pytest.mark.parametrize("client_count", [1, 2, 5])
@pytest.mark.asyncio
async def test_connect_listen(unused_tcp_port_factory, client_count):
    address = create_address(unused_tcp_port_factory)
    conn_queue = aio.Queue()

    with pytest.raises(Exception):
        await juggler.connect(address)

    srv = await juggler.listen(address,
                               lambda conn: conn_queue.put_nowait(conn))
    assert not srv.closed.done()

    conns = collections.deque()

    for i in range(client_count):
        conn = await juggler.connect(address)
        srv_conn = await conn_queue.get()

        conns.append((conn, srv_conn))

    while conns:
        conn, srv_conn = conns.popleft()

        assert not conn.closed.done()
        assert not srv_conn.closed.done()

        await conn.async_close()

        assert conn.closed.done()
        assert srv_conn.closed.done()

    assert not srv.closed.done()

    await srv.async_close()
    assert srv.closed.done()

    with pytest.raises(Exception):
        await juggler.connect(address)


@pytest.mark.parametrize("client_count", [1, 2, 10])
@pytest.mark.asyncio
async def test_srv_close_active_client(unused_tcp_port_factory, client_count):
    address = create_address(unused_tcp_port_factory)
    conn_closed_futures = []

    srv = await juggler.listen(address, lambda conn: None)

    for _ in range(client_count):
        conn = await juggler.connect(address)
        conn_closed_futures.append(conn.closed)

    await asyncio.wait_for(srv.async_close(), 0.1)
    assert srv.closed.done()

    await asyncio.wait_for(asyncio.gather(*conn_closed_futures), 0.1)


@pytest.mark.parametrize("data", [
    [True, False, True, False],
    [0, 1, 2, 3, 4, 5],
    [{}, {'a': 1}, {'a': 2}, {'a': 2, 'b': None}, {'b': None}],
    [0, False, '', [], {}, None]])
@pytest.mark.asyncio
async def test_set_local_data(client_server_connection, data,
                              short_sync_local_delay):
    conns = []

    for conn in client_server_connection:
        assert conn.local_data is None
        assert conn.remote_data is None
        change_queue = aio.Queue()
        conn.register_change_cb(lambda: change_queue.put_nowait(None))
        conns.append((conn, change_queue))

    for i in data:
        for local, remote in itertools.permutations(conns):
            local_conn, _ = local
            remote_conn, change_queue = remote

            local_conn.set_local_data(i)
            assert local_conn.local_data == i

            await change_queue.get()
            assert json.equals(remote_conn.remote_data, local_conn.local_data)


@pytest.mark.asyncio
async def test_flush_local_data(client_server_connection,
                                long_sync_local_delay):
    local_conn, remote_conn = client_server_connection
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
@pytest.mark.asyncio
async def test_send_receive(client_server_connection, messages):
    for send_msg in messages:
        for local_conn, remote_conn in itertools.permutations(
                client_server_connection):

            await local_conn.send(send_msg)

            rcv_msg = await remote_conn.receive()
            assert json.equals(send_msg, rcv_msg)


@pytest.mark.asyncio
async def test_big_message_server_to_client(client_server_connection):
    client_conn, server_conn = client_server_connection

    big_msg = '1' * 4194304 * 2
    await server_conn.send(big_msg)
    assert big_msg == await client_conn.receive()


@pytest.mark.asyncio
async def test_connection_closed(client_server_connection):
    local_conn, remote_conn = client_server_connection

    await remote_conn.async_close()

    with pytest.raises(juggler.ConnectionClosedError):
        await local_conn.send([])
    with pytest.raises(juggler.ConnectionClosedError):
        await local_conn.receive()
    with pytest.raises(juggler.ConnectionClosedError):
        local_conn.set_local_data([])
    with pytest.raises(juggler.ConnectionClosedError):
        await local_conn.flush_local_data()
