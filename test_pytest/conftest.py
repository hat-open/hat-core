import asyncio

import pytest

from hat import aio
from hat import util


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


def pytest_configure(config):
    aio.init_asyncio()


@pytest.fixture
def unused_udp_port(unused_udp_port_factory):
    return unused_udp_port_factory()


@pytest.fixture
def unused_udp_port_factory():
    return util.get_unused_udp_port
