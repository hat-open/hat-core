from pathlib import Path
import contextlib
import pytest
import socket

from hat import duktape
from hat import sbs
from hat.doit.hat_core.duktape import lib_path as duktape_lib_path
from hat.util import aio
from hat.util import json


def pytest_configure(config):
    aio.init_asyncio()

    root_path = Path(__file__).parent.parent
    json.default_schemas_json_path = root_path / 'schemas_json'
    sbs.default_schemas_sbs_path = root_path / 'schemas_sbs'
    duktape.default_duktape_path = (Path(__file__).parent.parent /
                                    duktape_lib_path)


@pytest.fixture
def unused_udp_port(unused_udp_port_factory):
    return unused_udp_port_factory()


@pytest.fixture
def unused_udp_port_factory():

    def unused_udp_port_factory():
        with contextlib.closing(socket.socket(type=socket.SOCK_DGRAM)) as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]

    return unused_udp_port_factory
