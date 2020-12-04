import pytest
from test_unit.test_gui import common

from hat import json
import hat.gui.view


@pytest.fixture
def view_factory(tmp_path_factory):
    def factory(view_name, file_descriptors, conf=None):
        view_path = tmp_path_factory.mktemp(view_name)
        conf_path = None
        if conf is not None:
            conf_path = tmp_path_factory.mktemp('conf') / 'conf.yaml'
        common.create_view_files(view_path, file_descriptors, conf_path, conf)
        return {'name': view_name,
                'view_path': str(view_path),
                'conf_path': None if conf is None else str(conf_path)}

    return factory


@pytest.fixture
async def view_manager_factory():
    managers = []

    async def factory(conf, schema_repo=None):
        if schema_repo is None:
            schema_repo = json.SchemaRepository()
        manager = await hat.gui.view.create_view_manager(conf, schema_repo)
        managers.append(manager)
        return manager
        await manager.async_close()

    yield factory
    for manager in managers:
        await manager.async_close()
