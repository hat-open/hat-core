import collections
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


def test_equals_example():
    assert json.equals(0, 0.0) is True
    assert json.equals({'a': 1, 'b': 2}, {'b': 2, 'a': 1}) is True
    assert json.equals(1, True) is False


def test_clone_example():
    x = {'a': [1, 2, 3]}
    y = json.clone(x)
    assert x is not y
    assert x['a'] is not y['a']
    assert json.equals(x, y)


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


def test_flatten_example():
    data = [1, [], [2], {'a': [3]}]
    result = [1, 2, {'a': [3]}]
    assert list(json.flatten(data)) == result


@pytest.mark.parametrize("data, path, default, result", [
    (123,
     [],
     None,
     123),

    ('abc',
     [1, 'a', 2, 'b', 3],
     None,
     None),

    ({'a': [{'b': 1}, 2, 3]},
     ['a', 0, 'b'],
     None,
     1),

    ([1, 2, 3],
     0,
     None,
     1),

    ([1, 2, 3],
     -1,
     None,
     3),

    ([1, 2, 3],
     3,
     None,
     None),

    ([1, 2, 3],
     -4,
     None,
     None),

    ([1, 2, 3],
     -4,
     123,
     123),

    ([1, 2, 3],
     ['a'],
     'abc',
     'abc'),

    ({'a': 3},
     ['c'],
     456,
     456),

    ({'a': 3},
     [0],
     456,
     456),

    ({'a': [{'b': 1}, 2, 3]},
     ['a', 0, 'b', 0],
     [1, 2],
     [1, 2]),

    (None,
     ['a', 'b'],
     {'b': 123},
     {'b': 123})
])
def test_get(data, path, default, result):
    x = json.get(data, path, default)
    assert json.equals(x, result)


def test_get_example():
    data = {'a': [1, 2, [3, 4]]}
    path = ['a', 2, 0]
    assert json.get(data, path) == 3

    data = [1, 2, 3]
    assert json.get(data, 0) == 1
    assert json.get(data, 5) is None


def test_get_invalid_path():
    with pytest.raises(ValueError):
        json.get(None, True)


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


def test_set_example():
    data = [1, {'a': 2, 'b': 3}, 4]
    path = [1, 'b']
    result = json.set_(data, path, 5)
    assert result == [1, {'a': 2, 'b': 5}, 4]
    assert result is not data

    data = [1, 2, 3]
    result = json.set_(data, 4, 4)
    assert result == [1, 2, 3, None, 4]


def test_set_invalid_path():
    with pytest.raises(ValueError):
        json.set_(None, True, 1)


@pytest.mark.parametrize("data, path, result", [
    (None,
     [],
     None),

    (123,
     [],
     None),

    ([1, {}, 'abc'],
     [],
     None),

    ([1, 2, 3],
     1,
     [1, 3]),

    ({'a': 1, 'b': 2},
     'a',
     {'b': 2}),

    ([1, {'a': [2, 3]}],
     [1, 'a', 0],
     [1, {'a': [3]}]),

    (123,
     123,
     123),

    ([1, 2, 3],
     5,
     [1, 2, 3]),

    ({'a': 123},
     'b',
     {'a': 123})
])
def test_remove(data, path, result):
    x = json.remove(data, path)
    assert json.equals(x, result)


def test_remove_example():
    data = [1, {'a': 2, 'b': 3}, 4]
    path = [1, 'b']
    result = json.remove(data, path)
    assert result == [1, {'a': 2}, 4]
    assert result is not data

    data = [1, 2, 3]
    result = json.remove(data, 4)
    assert result == [1, 2, 3]


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


def test_diff_example():
    src = [1, {'a': 2}, 3]
    dst = [1, {'a': 4}, 3]
    result = json.diff(src, dst)
    assert result == [{'op': 'replace', 'path': '/1/a', 'value': 4}]


def test_patch_example():
    data = [1, {'a': 2}, 3]
    d = [{'op': 'replace', 'path': '/1/a', 'value': 4}]
    result = json.patch(data, d)
    assert result == [1, {'a': 4}, 3]


@pytest.mark.parametrize('format', list(json.Format))
@pytest.mark.parametrize('indent', [None, 4])
@pytest.mark.parametrize('data', [
    None,
    True,
    False,
    1,
    1.0,
    'abc',
    [1, 2, 3],
    {'a': [[], []]}
])
def test_encode_decode(format, indent, data):
    encoded = json.encode(data, format, indent)
    decoded = json.decode(encoded, format)
    assert data == decoded


@pytest.mark.parametrize('format', list(json.Format))
@pytest.mark.parametrize('indent', [None, 4])
@pytest.mark.parametrize('data', [
    None,
    True,
    False,
    1,
    1.0,
    'abc',
    [1, 2, 3],
    {'a': [[], []]}
])
def test_encode_decode_file(tmp_path, format, indent, data):
    path = tmp_path / 'data'
    json.encode_file(data, path, format, indent)
    decoded = json.decode_file(path, format)
    assert data == decoded

    if format == json.Format.JSON:
        path = path.with_suffix('.json')
    elif format == json.Format.YAML:
        path = path.with_suffix('.yaml')
    else:
        raise NotImplementedError()
    json.encode_file(data, path, None, indent)
    decoded = json.decode_file(path, None)
    assert data == decoded


def test_storage():
    data_queue = collections.deque()
    storage = json.Storage(123)
    storage.register_change_cb(data_queue.append)

    assert storage.data == 123
    assert storage.get([]) == 123

    storage.set(['a', 'b', 'c'], 123)
    assert storage.data == {'a': {'b': {'c': 123}}}
    assert storage.get(['a', 'b', 'c']) == 123
    assert data_queue.pop() == {'a': {'b': {'c': 123}}}

    storage.remove(['a', 'b', 'c'])
    assert storage.data == {'a': {'b': {}}}
    assert storage.get(['a', 'b', 'c']) is None
    assert data_queue.pop() == {'a': {'b': {}}}

    assert not data_queue


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
