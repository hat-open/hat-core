"""JSON data manipulation and validation"""

import collections
import enum
import io
import itertools
import json
import pathlib
import typing
import urllib.parse

import jsonpatch
import jsonschema.validators
import yaml


Array: typing.Type = typing.List['Data']
Object: typing.Type = typing.Dict[str, 'Data']
Data: typing.Type = typing.Union[None, bool, int, float, str, Array, Object]
"""JSON data type identifier."""

Format = enum.Enum('Format', ['JSON', 'YAML'])
"""Encoding format"""

Path: typing.Type = typing.Union[int, str, typing.List['Path']]
"""Data path"""


def equals(a: Data,
           b: Data
           ) -> bool:
    """Equality comparison of json serializable data.

    Tests for equality of data according to JSON format. Notably, ``bool``
    values are not considered equal to numeric values in any case. This is
    different from default equality comparison, which considers `False`
    equal to `0` and `0.0`; and `True` equal to `1` and `1.0`.

    Example::

        assert equals(0, 0.0) is True
        assert equals({'a': 1, 'b': 2}, {'b': 2, 'a': 1}) is True
        assert equals(1, True) is False

    """
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if a != b:
        return False

    if isinstance(a, dict):
        return all(equals(a[key], b[key]) for key in a)
    elif isinstance(a, list):
        return all(equals(i, j) for i, j in zip(a, b))
    else:
        return True


def flatten(data: Data
            ) -> typing.Iterable[Data]:
    """Flatten JSON data

    If `data` is array, this generator recursively yields result of `flatten`
    call with each element of input list. For other `Data` types, input data is
    yielded.

    Example::

        data = [1, [], [2], {'a': [3]}]
        result = [1, 2, {'a': [3]}]
        assert list(flatten(data)) == result

    """
    if isinstance(data, list):
        for i in data:
            yield from flatten(i)
    else:
        yield data


def get(data: Data,
        path: Path,
        default: typing.Optional[Data] = None
        ) -> Data:
    """Get data element referenced by path

    Example::

        data = {'a': [1, 2, [3, 4]]}
        path = ['a', 2, 0]
        assert get(data, path) == 3

        data = [1, 2, 3]
        assert get(data, 0) == 1
        assert get(data, 5) is None
        assert get(data, 5, default=123) == 123

    """
    for i in flatten(path):
        if isinstance(i, str):
            if not isinstance(data, dict) or i not in data:
                return default
            data = data[i]

        elif isinstance(i, int) and not isinstance(i, bool):
            if not isinstance(data, list):
                return default
            try:
                data = data[i]
            except IndexError:
                return default

        else:
            raise ValueError('invalid path')

    return data


def set_(data: Data,
         path: Path,
         value: Data
         ) -> Data:
    """Create new data by setting data path element value

    Example::

        data = [1, {'a': 2, 'b': 3}, 4]
        path = [1, 'b']
        result = set_(data, path, 5)
        assert result == [1, {'a': 2, 'b': 5}, 4]
        assert result is not data

        data = [1, 2, 3]
        result = set_(data, 4, 4)
        assert result == [1, 2, 3, None, 4]

    """
    parents = collections.deque()

    for i in flatten(path):
        parent = data

        if isinstance(i, str):
            data = data.get(i) if isinstance(data, dict) else None

        elif isinstance(i, int) and not isinstance(i, bool):
            try:
                data = data[i] if isinstance(data, list) else None
            except IndexError:
                data = None

        else:
            raise ValueError('invalid path')

        parents.append((parent, i))

    while parents:
        parent, i = parents.pop()

        if isinstance(i, str):
            parent = dict(parent) if isinstance(parent, dict) else {}
            parent[i] = value

        elif isinstance(i, int) and not isinstance(i, bool):
            if not isinstance(parent, list):
                parent = []

            if i >= len(parent):
                parent = [*parent,
                          *itertools.repeat(None, i - len(parent) + 1)]

            elif i < 0 and (-i) > len(parent):
                parent = [*itertools.repeat(None, (-i) - len(parent)),
                          *parent]

            else:
                parent = list(parent)

            parent[i] = value

        else:
            raise ValueError('invalid path')

        value = parent

    return value


def diff(src: Data,
         dst: Data
         ) -> Data:
    """Generate JSON Patch diff.

    Example::

        src = [1, {'a': 2}, 3]
        dst = [1, {'a': 4}, 3]
        result = diff(src, dst)
        assert result == [{'op': 'replace', 'path': '/1/a', 'value': 4}]

    """
    return jsonpatch.JsonPatch.from_diff(src, dst).patch


def patch(data: Data,
          diff: Data
          ) -> Data:
    """Apply JSON Patch diff.

    Example::

        data = [1, {'a': 2}, 3]
        d = [{'op': 'replace', 'path': '/1/a', 'value': 4}]
        result = patch(data, d)
        assert result == [1, {'a': 4}, 3]

    """
    return jsonpatch.apply_patch(data, diff)


def encode(data: Data,
           format: Format = Format.JSON,
           indent: typing.Optional[int] = None
           ) -> str:
    """Encode JSON data.

    Args:
        data: JSON data
        format: encoding format
        indent: indentation size

    """
    if format == Format.JSON:
        return json.dumps(data, indent=indent)

    if format == Format.YAML:
        dumper = (yaml.CSafeDumper if hasattr(yaml, 'CSafeDumper')
                  else yaml.SafeDumper)
        return str(yaml.dump(data, indent=indent, Dumper=dumper))

    raise ValueError('unsupported format')


def decode(data_str: str,
           format: Format = Format.JSON
           ) -> Data:
    """Decode JSON data.

    Args:
        data_str: encoded JSON data
        format: encoding format

    """
    if format == Format.JSON:
        return json.loads(data_str)

    if format == Format.YAML:
        loader = (yaml.CSafeLoader if hasattr(yaml, 'CSafeLoader')
                  else yaml.SafeLoader)
        return yaml.load(io.StringIO(data_str), Loader=loader)

    raise ValueError('unsupported format')


def encode_file(data: Data,
                path: pathlib.PurePath,
                format: typing.Optional[Format] = None,
                indent: typing.Optional[int] = 4):
    """Encode JSON data to file.

    If `format` is ``None``, encoding format is derived from path suffix.

    Args:
        data: JSON data
        path: file path
        format: encoding format
        indent: indentation size

    """
    if format is None:
        if path.suffix == '.json':
            format = Format.JSON
        elif path.suffix in ('.yaml', '.yml'):
            format = Format.YAML
        else:
            raise ValueError('can not determine format from path suffix')

    with open(path, 'w', encoding='utf-8') as f:
        if format == Format.JSON:
            json.dump(data, f, indent=indent)

        elif format == Format.YAML:
            dumper = (yaml.CSafeDumper if hasattr(yaml, 'CSafeDumper')
                      else yaml.SafeDumper)
            yaml.dump(data, f, indent=indent, Dumper=dumper,
                      explicit_start=True, explicit_end=True)

        else:
            raise ValueError('unsupported format')


def decode_file(path: pathlib.PurePath,
                format: typing.Optional[Format] = None
                ) -> Data:
    """Decode JSON data from file.

    If `format` is ``None``, encoding format is derived from path suffix.

    Args:
        path: file path
        format: encoding format

    """
    if format is None:
        if path.suffix == '.json':
            format = Format.JSON
        elif path.suffix in ('.yaml', '.yml'):
            format = Format.YAML
        else:
            raise ValueError('can not determine format from path suffix')

    with open(path, 'r', encoding='utf-8') as f:
        if format == Format.JSON:
            return json.load(f)

        if format == Format.YAML:
            loader = (yaml.CSafeLoader if hasattr(yaml, 'CSafeLoader')
                      else yaml.SafeLoader)
            return yaml.load(f, Loader=loader)

        raise ValueError('unsupported format')


class SchemaRepository:
    """JSON Schema repository.

    A repository that holds json schemas and enables validation against them.

    Repository can be initialized with multiple arguments, which can be
    instances of ``pathlib.PurePath``, ``Data`` or ``SchemaRepository``.

    If an argument is of type ``pathlib.PurePath``, and path points to file
    with a suffix '.json', '.yml' or '.yaml', json serializable data is decoded
    from the file. Otherwise, it is assumed that path points to a directory,
    which is recursively searched for json and yaml files. All decoded schemas
    are added to the repository. If a schema with the same `id` was previosly
    added, an exception is raised.

    If an argument is of type ``Data``, it should be a json serializable data
    representation of a JSON schema. If a schema with the same `id` was
    previosly added, an exception is raised.

    If an argument is of type ``SchemaRepository``, its schemas are added to
    the new repository. Previously added schemas with the same `id` are
    replaced.

    """

    def __init__(self, *args: typing.Union[pathlib.PurePath,
                                           Data,
                                           'SchemaRepository']):
        self._data = {}
        for arg in args:
            if isinstance(arg, pathlib.PurePath):
                self._load_path(arg)
            elif isinstance(arg, SchemaRepository):
                self._load_repository(arg)
            else:
                self._load_schema(arg)

    def validate(self,
                 schema_id: str,
                 data: Data):
        """Validate data against JSON schema.

        Args:
            schema_id: JSON schema identifier
            data: data to be validated

        Raises:
            jsonschema.ValidationError

        """
        uri = urllib.parse.urlparse(schema_id)
        path = uri.netloc + uri.path
        resolver = jsonschema.RefResolver(
            base_uri=f'{uri.scheme}://{path}',
            referrer=self._data[uri.scheme][path],
            handlers={i: self._get_schema
                      for i in self._data.keys()})
        jsonschema.validate(
            instance=data,
            schema=resolver.resolve_fragment(resolver.referrer, uri.fragment),
            resolver=resolver)

    def to_json(self) -> Data:
        """Export repository content as json serializable data.

        Entire repository content is exported as json serializable data.
        New repository can be created from the exported content by using
        :meth:`SchemaRepository.from_json`.

        """
        return self._data

    @staticmethod
    def from_json(data: typing.Union[pathlib.PurePath,
                                     Data]
                  ) -> 'SchemaRepository':
        """Create new repository from content exported as json serializable
        data.

        Creates a new repository from content of another repository that was
        exported by using :meth:`SchemaRepository.to_json`.

        Args:
            data: repository data

        """
        if isinstance(data, pathlib.PurePath):
            data = decode_file(data)
        repo = SchemaRepository()
        repo._data = data
        return repo

    def _get_schema(self, scheme_id):
        uri = urllib.parse.urlparse(scheme_id)
        path = uri.netloc + uri.path
        return self._data[uri.scheme][path]

    def _load_path(self, path):
        json_suffixes = {'.json', '.yaml', '.yml'}
        paths = ([path] if path.suffix in json_suffixes
                 else list(itertools.chain.from_iterable(
                    path.rglob(f'*{i}') for i in json_suffixes)))
        for path in paths:
            schema = decode_file(path)
            self._load_schema(schema)

    def _load_schema(self, schema):
        meta_schema_id = urllib.parse.urldefrag(schema.get('$schema', '')).url
        if meta_schema_id not in jsonschema.validators.meta_schemas:
            meta_schema_id = jsonschema.Draft7Validator.META_SCHEMA['$schema']
            schema = dict(schema)
            schema['$schema'] = meta_schema_id

        uri = urllib.parse.urlparse(schema['id'])
        path = uri.netloc + uri.path
        if uri.scheme not in self._data:
            self._data[uri.scheme] = {}
        if path in self._data[uri.scheme]:
            raise Exception(f"duplicate schema id {uri.scheme}://{path}")
        self._data[uri.scheme][path] = schema

    def _load_repository(self, repo):
        for k, v in repo._data.items():
            if k not in self._data:
                self._data[k] = v
            else:
                self._data[k].update(v)


_json_schema_repo_path = (pathlib.Path(__file__).parent /
                          'json_schema_repo.json')

json_schema_repo: SchemaRepository = (
    SchemaRepository.from_json(_json_schema_repo_path)
    if _json_schema_repo_path.exists()
    else SchemaRepository())
"""JSON Schema repository with generic schemas"""


# check upstream changes in jsonpatch and validate performance inpact

# def _monkeypatch_jsonpatch():
#     """Monkeypatch jsonpatch.

#     Patch incorrect value comparison between ``bool`` and numeric values when
#     diffing json serializable data.

#     Comparing `False` to `0` or `0.0`; and `True` to `1` or `1.0` incorrectly
#     results in no change.

#     """
#     def _compare_values(self, path, key, src, dst):

#         if isinstance(src, jsonpatch.MutableMapping) and \
#                 isinstance(dst, jsonpatch.MutableMapping):
#             self._compare_dicts(jsonpatch._path_join(path, key), src, dst)

#         elif isinstance(src, jsonpatch.MutableSequence) and \
#                 isinstance(dst, jsonpatch.MutableSequence):
#             self._compare_lists(jsonpatch._path_join(path, key), src, dst)

#         elif isinstance(src, bool) == isinstance(dst, bool) and src == dst:
#             pass

#         else:
#             self._item_replaced(path, key, dst)

#     jsonpatch.DiffBuilder._compare_values = _compare_values


# _monkeypatch_jsonpatch()
