import asyncio

import pytest

from hat import sbs
from hat import chatter
import pem


pytestmark = pytest.mark.asyncio


@pytest.fixture
def pem_path(tmp_path):
    path = tmp_path / 'pem'
    pem.create_pem_file(path)
    return path


@pytest.fixture(scope="session")
def sbs_repo():
    data_sbs_repo = sbs.Repository("""
        module Test

        Data = Integer
    """)
    return sbs.Repository(chatter.sbs_repo, data_sbs_repo)


async def test_sbs_repo(sbs_repo):
    data = 123
    encoded_data = sbs_repo.encode('Test', 'Data', data)
    decoded_data = sbs_repo.decode('Test', 'Data', encoded_data)
    assert data == decoded_data

    msg = {'id': 1,
           'first': 2,
           'owner': True,
           'token': False,
           'last': True,
           'data': {'module': ('Just', 'Test'),
                    'type': 'Data',
                    'data': encoded_data}}
    encoded_msg = sbs_repo.encode('Hat', 'Msg', msg)
    decoded_msg = sbs_repo.decode('Hat', 'Msg', encoded_msg)
    assert msg == decoded_msg


async def test_connect(sbs_repo, unused_tcp_port):
    address = f'tcp+sbs://[::1]:{unused_tcp_port}'

    with pytest.raises(Exception):
        await chatter.connect(sbs_repo, address)

    srv_conn_future = asyncio.Future()
    srv = await chatter.listen(sbs_repo, address,
                               lambda conn: srv_conn_future.set_result(conn))
    conn = await chatter.connect(sbs_repo, address)
    srv_conn = await srv_conn_future

    assert not conn.is_closed
    assert not srv_conn.is_closed
    assert srv.addresses == [address]
    assert conn.remote_address == address
    assert srv_conn.local_address == address

    await conn.async_close()
    await srv.async_close()

    assert conn.is_closed
    assert srv_conn.is_closed


async def test_ssl_connect(sbs_repo, unused_tcp_port, pem_path):
    address = f'ssl+sbs://127.0.0.1:{unused_tcp_port}'
    srv = await chatter.listen(sbs_repo, address, lambda conn: None,
                               pem_file=pem_path)

    conn_without_cert = await chatter.connect(sbs_repo, address)
    assert not conn_without_cert.is_closed
    await conn_without_cert.async_close()
    assert conn_without_cert.is_closed

    conn_with_cert = await chatter.connect(sbs_repo, address,
                                           pem_file=pem_path)
    assert not conn_with_cert.is_closed
    await conn_with_cert.async_close()
    assert conn_with_cert.is_closed

    await srv.async_close()


async def test_listen(sbs_repo, unused_tcp_port):
    address = f'tcp+sbs://127.0.0.1:{unused_tcp_port}'

    srv = await chatter.listen(sbs_repo, address, lambda conn: None)
    assert not srv.is_closed

    conn = await chatter.connect(sbs_repo, address)
    await conn.async_close()

    await srv.async_close()
    assert srv.is_closed

    with pytest.raises(Exception):
        await chatter.connect(sbs_repo, address)


async def test_wrong_address(sbs_repo, unused_tcp_port):
    addresses = ['tcp+sbs://127.0.0.1',
                 f'tcp://127.0.0.1:{unused_tcp_port}']

    for address in addresses:
        with pytest.raises(ValueError):
            await chatter.connect(sbs_repo, address)

        with pytest.raises(ValueError):
            await chatter.listen(sbs_repo, address, lambda conn: None)


async def test_send_receive(sbs_repo, unused_tcp_port):
    address = f'tcp+sbs://127.0.0.1:{unused_tcp_port}'
    conn2_future = asyncio.Future()
    srv = await chatter.listen(sbs_repo, address,
                               lambda conn: conn2_future.set_result(conn))
    conn1 = await chatter.connect(sbs_repo, address)
    conn2 = await conn2_future

    data = chatter.Data(module='Test',
                        type='Data',
                        data=123)
    conv = conn1.send(data)
    assert conv.owner is True
    msg = await conn2.receive()
    assert msg.data == data
    assert msg.conv.owner is False
    assert msg.conv.first_id == conv.first_id
    assert msg.first is True
    assert msg.last is True
    assert msg.token is True

    await conn1.async_close()
    await conn2.async_close()
    await srv.async_close()

    with pytest.raises(ConnectionError):
        conn1.send(data)
    with pytest.raises(ConnectionError):
        await conn2.receive()


async def test_send_receive_native_data(sbs_repo, unused_tcp_port):
    address = f'tcp+sbs://127.0.0.1:{unused_tcp_port}'
    conn2_future = asyncio.Future()
    srv = await chatter.listen(sbs_repo, address,
                               lambda conn: conn2_future.set_result(conn))
    conn1 = await chatter.connect(sbs_repo, address)
    conn2 = await conn2_future

    data = chatter.Data(module=None,
                        type='Integer',
                        data=123)
    conn1.send(data)
    msg = await conn2.receive()
    assert data == msg.data

    await conn1.async_close()
    await conn2.async_close()
    await srv.async_close()


async def test_invalid_communication(sbs_repo, unused_tcp_port):
    address = f'tcp+sbs://127.0.0.1:{unused_tcp_port}'
    conn_future = asyncio.Future()
    srv = await chatter.listen(sbs_repo, address,
                               lambda conn: conn_future.set_result(conn))
    reader, writer = await asyncio.open_connection('127.0.0.1',
                                                   unused_tcp_port)
    conn = await conn_future

    writer.write(b'\x01\x02\x03\x04')
    await writer.drain()
    with pytest.raises(ConnectionError):
        await conn.receive()

    writer.close()
    await writer.wait_closed()

    await conn.wait_closed()
    await srv.async_close()


async def test_conversation_timeout(sbs_repo, unused_tcp_port):
    address = f'tcp+sbs://127.0.0.1:{unused_tcp_port}'
    conn2_future = asyncio.Future()
    srv = await chatter.listen(sbs_repo, address,
                               lambda conn: conn2_future.set_result(conn))
    conn1 = await chatter.connect(sbs_repo, address)
    conn2 = await conn2_future

    data = chatter.Data(module='Test',
                        type='Data',
                        data=123)

    timeout = asyncio.Future()
    conv = conn1.send(data, last=False, timeout=1,
                      timeout_cb=lambda conv: timeout.set_result(conv))
    msg = await conn2.receive()
    conn2.send(data, last=False, conv=msg.conv)
    msg = await conn1.receive()

    assert msg.conv == conv

    conn1.send(data, last=False, token=False, timeout=0.001, conv=conv,
               timeout_cb=lambda conv: timeout.set_result(conv))
    conn1.send(data, last=False, timeout=0.001, conv=conv,
               timeout_cb=lambda conv: timeout.set_result(conv))
    assert not timeout.done()
    await timeout

    await conn1.async_close()
    await conn2.async_close()
    await srv.async_close()


async def test_ping_timeout(sbs_repo, unused_tcp_port):
    address = f'tcp+sbs://127.0.0.1:{unused_tcp_port}'
    conn_future = asyncio.Future()
    srv = await chatter.listen(sbs_repo, address,
                               lambda conn: conn_future.set_result(conn),
                               ping_timeout=0.001)
    reader, writer = await asyncio.open_connection('127.0.0.1',
                                                   unused_tcp_port)
    conn = await conn_future

    await conn.wait_closed()

    writer.close()
    await writer.wait_closed()

    await srv.async_close()


async def test_connection_close_when_queue_blocking(sbs_repo, unused_tcp_port):
    address = f'tcp+sbs://127.0.0.1:{unused_tcp_port}'
    conn2_future = asyncio.Future()
    srv = await chatter.listen(sbs_repo, address,
                               lambda conn: conn2_future.set_result(conn))
    conn1 = await chatter.connect(sbs_repo, address, queue_maxsize=1)
    conn2 = await conn2_future

    data = chatter.Data(module='Test',
                        type='Data',
                        data=123)
    conn2.send(data)
    conn2.send(data)

    await asyncio.sleep(0.01)

    await conn1.async_close()
    await asyncio.wait_for(conn2.wait_closed(), 0.1)

    await srv.async_close()


async def test_example_docs():

    from hat import aio
    from hat import chatter
    from hat import sbs
    from hat import util

    sbs_repo = sbs.Repository(chatter.sbs_repo, r"""
        module Example

        Msg = Integer
    """)

    port = util.get_unused_tcp_port()
    address = f'tcp+sbs://127.0.0.1:{port}'

    server_conns = aio.Queue()
    server = await chatter.listen(sbs_repo, address, server_conns.put_nowait)

    client_conn = await chatter.connect(sbs_repo, address)
    server_conn = await server_conns.get()

    data = chatter.Data('Example', 'Msg', 123)
    client_conn.send(data)

    msg = await server_conn.receive()
    assert msg.data == data

    await server.async_close()
    await client_conn.wait_closed()
    await server_conn.wait_closed()
