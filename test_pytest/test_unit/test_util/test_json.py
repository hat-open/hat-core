import itertools

import pytest

from hat.util import json


@pytest.mark.parametrize("params,is_equal", [
    ((0, 0.0), True),
    ((0, 1E-9), False),
    ((-100, -100.0), True),
    ((True, True), True),
    (('a', 'a'), True),
    (({'a': 0, 'b': 1}, {'b': 1, 'a': 0}), True),
    ((0, False, '', [], {}, None), False),
    (({'a': 0}, [0], 0), False),
    (([1, 2], [2, 1]), False),
    (([], [[]], [{}], [None], [0.0], [False], ['']), False),
    (({'a': None}, {'a': []}, {'a': {}}, {'a': 0}, {'a': False}, {'a': ''}),
     False)])
def test_json_equals(params, is_equal):
    for a, b in itertools.combinations(params, 2):
        assert json.equals(a, b) == is_equal


def test_jsonpatch():
    x = {'a': 0}
    y = {'a': False}
    diff = json.diff(x, y)
    assert diff == [{'op': 'replace', 'path': '/a', 'value': False}]


@pytest.mark.parametrize("x,y,diff", [
    ({'a': 0}, {'a': False},
     [{'op': 'replace', 'path': '/a', 'value': False}]),
    ({'a': ""}, {'a': False},
     [{'op': 'replace', 'path': '/a', 'value': False}]),
    ({'a': False}, {'a': False},
     []),
    ({'a': []}, {'a': {}},
     [{'op': 'replace', 'path': '/a', 'value': {}}]),
    ({'a': False}, {'a': None},
     [{'op': 'replace', 'path': '/a', 'value': None}]),
    ({'a': 1.0}, {'a': 1},
     []),
    ({'a': ""}, {'a': []},
     [{'op': 'replace', 'path': '/a', 'value': []}]),
    ({'a': {}}, {'a': {}},
     []),
    ({'a': ""}, {'a': ""},
     []),
    ({'a': []}, {'a': []},
     [])
])
def test_diff(x, y, diff):
    result = json.diff(x, y)
    assert result == diff


def test_schema_repository_init_empty():
    repo = json.SchemaRepository()
    assert not repo.to_json()


def test_schema_repository_init():
    schema = json.decode("id: 'xyz://abc'", format=json.Format.YAML)
    repo = json.SchemaRepository(schema)
    assert repo.to_json()


def test_schema_repository_init_duplicate_id():
    schema = json.decode("id: 'xyz://abc'", format=json.Format.YAML)
    repo = json.SchemaRepository(schema)
    assert repo.to_json() == json.SchemaRepository(repo, repo).to_json()
    with pytest.raises(Exception):
        json.SchemaRepository(schema, schema)


def test_schema_repository_init_paths(tmp_path):
    dir_path = tmp_path / 'repo'
    json_path = dir_path / 'schema.json'
    yaml_path = dir_path / 'schema.yaml'

    dir_path.mkdir()
    with open(json_path, 'w', encoding='utf-8') as f:
        f.write('{"id": "xyz1://abc1"}')
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write("id: 'xyz2://abc2'")
    repo1 = json.SchemaRepository(dir_path)
    repo2 = json.SchemaRepository(json_path, yaml_path)
    assert repo1.to_json() == repo2.to_json()


@pytest.mark.parametrize("schemas,schema_id,data", [
    ([r'''
        id: 'xyz://abc'
      '''],
     'xyz://abc#',
     None),
    ([r'''
        id: 'xyz://abc#'
      '''],
     'xyz://abc#',
     {'a': 'b'}),
    ([r'''
        id: 'xyz://abc#'
      '''],
     'xyz://abc',
     [1, 2, 3]),
    ([r'''
        id: 'xyz://abc1'
        type: object
        required:
            - a
            - c
        properties:
            a:
                '$ref': 'xyz://abc2#/definitions/value'
            c:
                '$ref': 'xyz://abc2'
      ''',
      r'''
        id: 'xyz://abc2'
        type: integer
        definitions:
            value:
                type: string
      '''],
     'xyz://abc1',
     {'a': 'b', 'c': 1})
])
def test_json_schema_repository_validate(schemas, schema_id, data):
    repo = json.SchemaRepository(*[json.decode(i, format=json.Format.YAML)
                                   for i in schemas])
    repo.validate(schema_id, data)


@pytest.mark.parametrize("schemas,schema_id,data", [
    ([r'''
        id: 'xyz://abc'
        type: integer
      '''],
     'xyz://abc',
     None)
])
def test_json_schema_repository_validate_invalid(schemas, schema_id, data):
    repo = json.SchemaRepository(*[json.decode(i, format=json.Format.YAML)
                                   for i in schemas])
    with pytest.raises(Exception):
        repo.validate(schema_id, data)
