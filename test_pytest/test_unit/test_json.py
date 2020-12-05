import itertools

import pytest

from hat import json


@pytest.mark.parametrize("params, is_equal", [
    ((0, 0.0),
     True),

    ((0, 1E-9),
     False),

    ((-100, -100.0),
     True),

    ((True, True),
     True),

    (('a', 'a'),
     True),

    (({'a': 0, 'b': 1},
      {'b': 1, 'a': 0}),
     True),

    ((0, False, '', [], {}, None),
     False),

    (({'a': 0}, [0], 0),
     False),

    (([1, 2], [2, 1]),
     False),

    (([], [[]], [{}], [None], [0.0], [False], ['']),
     False),

    (({'a': None},
      {'a': []},
      {'a': {}},
      {'a': 0},
      {'a': False},
      {'a': ''}),
     False)
])
def test_equals(params, is_equal):
    for a, b in itertools.combinations(params, 2):
        assert json.equals(a, b) == is_equal


@pytest.mark.parametrize("data, result", [
    (None,
     [None]),

    (1,
     [1]),

    (True,
     [True]),

    ('xyz',
     ['xyz']),

    ({'a': [1, [2, 3]]},
     [{'a': [1, [2, 3]]}]),

    ([],
     []),

    ([1, 2, 3],
     [1, 2, 3]),

    ([[[]], []],
     []),

    ([1, [2, [], [[], 3]]],
     [1, 2, 3])
])
def test_flatten(data, result):
    x = list(json.flatten(data))
    assert json.equals(x, result)


@pytest.mark.parametrize("data, path, result", [
    (123,
     [],
     123),

    ('abc',
     [1, 'a', 2, 'b', 3],
     None),

    ({'a': [{'b': 1}, 2, 3]},
     ['a', 0, 'b'],
     1),

    ([1, 2, 3],
     0,
     1),

    ([1, 2, 3],
     -1,
     3),

    ([1, 2, 3],
     3,
     None),

    ([1, 2, 3],
     -4,
     None)
])
def test_get(data, path, result):
    x = json.get(data, path)
    assert json.equals(x, result)


@pytest.mark.parametrize("data, path, value, result", [
    (123,
     [],
     'abc',
     'abc'),

    (None,
     ['a', 1],
     'x',
     {'a': [None, 'x']}),

    ({'a': [1, 2], 'b': 3},
     ['a', 1],
     4,
     {'a': [1, 4], 'b': 3}),

    ([1, 2, 3],
     4,
     'a',
     [1, 2, 3, None, 'a']),

    ([1, 2, 3],
     -5,
     'a',
     ['a', None, 1, 2, 3])
])
def test_set_(data, path, value, result):
    x = json.set_(data, path, value)
    assert json.equals(x, result)


@pytest.mark.parametrize("x, y, diff", [
    ({'a': 0},
     {'a': False},
     [{'op': 'replace', 'path': '/a', 'value': False}]),

    ({'a': ""},
     {'a': False},
     [{'op': 'replace', 'path': '/a', 'value': False}]),

    ({'a': False},
     {'a': False},
     []),

    ({'a': []},
     {'a': {}},
     [{'op': 'replace', 'path': '/a', 'value': {}}]),

    ({'a': False},
     {'a': None},
     [{'op': 'replace', 'path': '/a', 'value': None}]),

    # TODO should we consider 1 and 1.0 to be equal
    ({'a': 1.0},
     {'a': 1},
     [{'op': 'replace', 'path': '/a', 'value': 1.0}]),

    ({'a': ""},
     {'a': []},
     [{'op': 'replace', 'path': '/a', 'value': []}]),

    ({'a': {}},
     {'a': {}},
     []),

    ({'a': ""},
     {'a': ""},
     []),

    ({'a': []},
     {'a': []},
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


@pytest.mark.parametrize("schemas, schema_id, data", [
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


@pytest.mark.parametrize("schemas, schema_id, data", [
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
