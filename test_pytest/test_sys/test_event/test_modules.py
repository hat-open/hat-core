import asyncio

import pytest

import hat.event.client
import hat.event.common

from test_sys.test_event.modules import remote


@pytest.fixture
def remote_address(unused_tcp_port_factory):
    return f'tcp+sbs://127.0.0.1:{unused_tcp_port_factory()}'


@pytest.fixture
async def remote_msgs(remote_address):
    server = await remote.create_server(remote_address)
    yield server.queue
    await server.async_close()


@pytest.fixture
def mock_module_conf(remote_address):
    return {'module': 'test_sys.test_event.modules.remote',
            'subscriptions': [['*']],
            'address': remote_address}


@pytest.mark.asyncio
async def test_create_module(create_event_server, remote_msgs,
                             mock_module_conf):
    backend_conf = {'module': 'hat.event.server.backends.dummy'}
    modules_conf = [mock_module_conf]

    assert remote_msgs.empty()

    with create_event_server(backend_conf, modules_conf):
        msg = await asyncio.wait_for(remote_msgs.get(), 5)
        assert msg == 'ModuleCreate'
        assert remote_msgs.empty()

    msg = await asyncio.wait_for(remote_msgs.get(), 5)
    assert msg == 'ModuleClose'
    assert remote_msgs.empty()


@pytest.mark.asyncio
async def test_create_session(create_event_server, remote_msgs,
                              mock_module_conf):
    backend_conf = {'module': 'hat.event.server.backends.dummy'}
    modules_conf = [mock_module_conf]

    with create_event_server(backend_conf, modules_conf) as srv:

        msg = await asyncio.wait_for(remote_msgs.get(), 1)
        assert msg == 'ModuleCreate'

        srv.wait_active(1)

        client = await hat.event.client.connect(srv.address)
        client.register([hat.event.common.RegisterEvent(['a'], None, None)])

        msg = await asyncio.wait_for(remote_msgs.get(), 1)
        assert msg == 'SessionCreate'

        msg = await asyncio.wait_for(remote_msgs.get(), 1)
        assert msg == 'Process'

        msg = await asyncio.wait_for(remote_msgs.get(), 1)
        assert msg == 'SessionClose'

        await client.async_close()

    msg = await asyncio.wait_for(remote_msgs.get(), 1)
    assert msg == 'ModuleClose'


def test_invalid_module_conf(create_event_server):
    backend_conf = {'module': 'hat.event.server.backends.dummy'}
    modules_conf = [{'module': 'test_event.mock_module'}]

    with create_event_server(backend_conf, modules_conf,
                             ignore_stderr=True) as srv:
        with pytest.raises(Exception):
            srv.wait_active(1)
