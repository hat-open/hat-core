import pytest

from hat.event.server import common
import hat.event.server.backends.sqlite


pytestmark = pytest.mark.asyncio


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / 'sqlite.db'


async def test_create(db_path):
    conf = {'module': 'hat.event.server.backends.sqlite',
            'db_path': str(db_path),
            'query_pool_size': 1}
    backend = await hat.event.server.backends.sqlite.create(conf)

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
