import base64

import pytest

from hat import json
import hat.gui.view


pytestmark = pytest.mark.asyncio


async def test_empty_view_manager():
    conf = {'views': []}
    manager = await hat.gui.view.create_view_manager(conf)

    assert manager.is_open

    with pytest.raises(Exception):
        await manager.get('abc')

    await manager.async_close()


@pytest.mark.parametrize('files, data', [
    ({},
     {}),

    ({'a/b/c.txt': 'abc',
      'x.js': 'x',
      'y.css': 'y'},
     {'a/b/c.txt': 'abc',
      'x.js': 'x',
      'y.css': 'y'}),

    ({'a.json': '[1, true, null, {}]'},
     {'a.json': [1, True, None, {}]}),

    ({'test1.yaml': '1',
      'test2.yml': '2'},
     {'test1.yaml': 1,
      'test2.yml': 2}),

    ({'a.xml': '<a>123</a>',
      'b.svg': '<b1><b2>123</b2></b1>'},
     {'a.xml': ['a', '123'],
      'b.svg': ['b1', ['b2', '123']]}),

    ({'a.bin': '123'},
     {'a.bin': base64.b64encode(b'123').decode('utf-8')}),
])
async def test_view_data(tmp_path, files, data):
    name = 'name'
    conf = {'views': [{'name': name,
                       'view_path': str(tmp_path),
                       'conf_path': None}]}
    manager = await hat.gui.view.create_view_manager(conf)

    view = await manager.get(name)
    assert view.name == name
    assert view.conf is None
    assert view.data == {}

    for file_name, file_content in files.items():
        path = tmp_path / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(file_content)

    view = await manager.get(name)
    assert view.name == name
    assert view.conf is None
    assert view.data == data

    await manager.async_close()

    with pytest.raises(Exception):
        await manager.get(name)


async def test_invalid_view_path():
    name = 'name'
    conf = {'views': [{'name': name,
                       'view_path': None,
                       'conf_path': None}]}
    manager = await hat.gui.view.create_view_manager(conf)

    with pytest.raises(Exception):
        await manager.get(name)

    await manager.async_close()


async def test_validate_conf(tmp_path):
    name = 'name'
    conf_path = tmp_path / 'conf.json'
    schema_path = tmp_path / 'schema.json'
    conf = {'views': [{'name': name,
                       'view_path': str(tmp_path),
                       'conf_path': str(conf_path)}]}
    manager = await hat.gui.view.create_view_manager(conf)

    with pytest.raises(Exception):
        await manager.get(name)

    schema = {'id': 'test://schema',
              'type': 'object',
              'required': ['abc']}
    json.encode_file(schema, schema_path)

    with pytest.raises(Exception):
        await manager.get(name)

    data = {'cba': 123}
    json.encode_file(data, conf_path)

    with pytest.raises(Exception):
        await manager.get(name)

    data = {'abc': 321}
    json.encode_file(data, conf_path)

    view = await manager.get(name)
    assert view.name == name
    assert view.conf == data
    assert view.data == {conf_path.name: data,
                         schema_path.name: schema}

    await manager.async_close()
