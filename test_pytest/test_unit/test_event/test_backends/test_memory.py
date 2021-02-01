import pytest

from hat.event.server import common
import hat.event.server.backends.memory


pytestmark = pytest.mark.asyncio


async def test_create():
    conf = {'module': 'hat.event.server.backends.memory'}
    backend = await hat.event.server.backends.memory.create(conf)

    assert isinstance(backend, common.Backend)
    assert backend.is_open

    await backend.async_close()
    assert backend.is_closed


async def test_get_last_event_id():
    # TODO
    pass


async def test_register():
    # TODO
    pass


async def test_query():
    # TODO
    pass
