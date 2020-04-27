import pytest
import time

from hat import util


def test_run_single(create_event_server):
    backend_conf = {'module': 'hat.event.server.backends.dummy'}
    modules_conf = []

    with create_event_server(backend_conf, modules_conf) as srv:
        srv.wait_active(1)


@pytest.mark.parametrize("srv_count", [1, 2, 5])
def test_run_multiple(create_event_server, srv_count):
    backend_conf = {'module': 'hat.event.server.backends.dummy'}
    modules_conf = []

    def wait_active_server(servers, timeout):
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            srv = util.first(servers, lambda srv: srv.is_active())
            if srv:
                return srv
            time.sleep(0.01)

    servers = set()
    for _ in range(srv_count):
        srv = create_event_server(backend_conf, modules_conf)
        servers.add(srv)

    while servers:
        active_srv = wait_active_server(servers, 5)
        assert active_srv
        for srv in servers:
            if srv is not active_srv:
                assert not srv.is_active()
        servers.remove(active_srv)
        active_srv.close()
