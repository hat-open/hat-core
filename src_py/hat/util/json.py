"""JSON data manipulation and validation

Attributes:
    default_schemas_json_path (pathlib.Path):
        Default path to schemas_json directory.
    Data: JSON data type identifier.

"""

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

from hat import util


default_schemas_json_path = pathlib.Path(__file__).parent / 'schemas_json'


Data = typing.Union[None, bool, int, float, str,
                    typing.List['Data'],
                    typing.Dict[str, 'Data']]

Format = util.extend_enum_doc(enum.Enum('Format', ['JSON', 'YAML']))


def equals(a, b):
    """Equality comparison of json serializable data.

    Tests for equality of data according to JSON format. Notably, ``bool``
    values are not considered equal to numeric values in any case. This is
    different from default equality comparison, which considers `False`
    equal to `0` and `0.0`; and `True` equal to `1` and `1.0`.

    Args:
        a (Data): data
        b (Data): data

    Returns:
        bool

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


def diff(src, dst):
    """Generate JSON Patch diff.

    Args:
        src (Data): data
        dst (Data): data

    Returns:
        Data

    """
    return jsonpatch.JsonPatch.from_diff(src, dst).patch


def patch(data, diff):
    """Apply JSON Patch diff.

    Args:
        data (Data): data
        diff (Data): diff

    Returns:
        Data

    """
    return jsonpatch.apply_patch(data, diff)


def encode(data, format=Format.JSON, indent=None):
    """Encode JSON data.

    Args:
        data (Data): JSON data
        format (Format): encoding format
        indent (Optional[int]): indentation size

    Returns:
        str

    """
    if format == Format.JSON:
        return json.dumps(data, indent=indent)

    if format == Format.YAML:
        dumper = (yaml.CSafeDumper if hasattr(yaml, 'CSafeDumper')
                  else yaml.SafeDumper)
        return str(yaml.dump(data, indent=indent, Dumper=dumper))

    raise ValueError()


def decode(data_str, format=Format.JSON):
    """Decode JSON data.

    Args:
        data_str (str): encoded JSON data
        format (Format): encoding format

    Returns:
        Data

    """
    if format == Format.JSON:
        return json.loads(data_str)

    if format == Format.YAML:
        loader = (yaml.CSafeLoader if hasattr(yaml, 'CSafeLoader')
                  else yaml.SafeLoader)
        return yaml.load(io.StringIO(data_str), Loader=loader)

    raise ValueError()


def encode_file(data, path, format=None, indent=4):
    """Encode JSON data to file.

    If format is `None`, encoding format is derived from path suffix.

    Args:
        data (Data): JSON data
        path (pathlib.PurePath): file path
        format (Optional[Format]): encoding format
        indent (Optional[int]): indentation size

    """
    if format is None:
        if path.suffix == '.json':
            format = Format.JSON
        elif path.suffix in ('.yaml', '.yml'):
            format = Format.YAML
        else:
            raise ValueError()

    with open(path, 'w', encoding='utf-8') as f:
        if format == Format.JSON:
            json.dump(data, f, indent=indent)

        elif format == Format.YAML:
            dumper = (yaml.CSafeDumper if hasattr(yaml, 'CSafeDumper')
                      else yaml.SafeDumper)
            yaml.dump(data, f, indent=indent, Dumper=dumper,
                      explicit_start=True, explicit_end=True)

        else:
            raise ValueError()


def decode_file(path, format=None):
    """Decode JSON data from file.

    If format is `None`, encoding format is derived from path suffix.

    Args:
        path (pathlib.PurePath): file path
        format (Optional[Format]): encoding format

    Returns:
        Data

    """
    if format is None:
        if path.suffix == '.json':
            format = Format.JSON
        elif path.suffix in ('.yaml', '.yml'):
            format = Format.YAML
        else:
            raise ValueError()

    with open(path, 'r', encoding='utf-8') as f:
        if format == Format.JSON:
            return json.load(f)

        if format == Format.YAML:
            loader = (yaml.CSafeLoader if hasattr(yaml, 'CSafeLoader')
                      else yaml.SafeLoader)
            return yaml.load(f, Loader=loader)

        raise ValueError()


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

    Args:
        args (Union[pathlib.PurePath,Data,SchemaRepository]): init arguments

    """

    def __init__(self, *args):
        self._data = {}
        for arg in args:
            if isinstance(arg, pathlib.PurePath):
                self._load_path(arg)
            elif isinstance(arg, SchemaRepository):
                self._load_repository(arg)
            else:
                self._load_schema(arg)

    def validate(self, schema_id, data):
        """Validate data against JSON schema.

        Args:
            schema_id (str): JSON schema identifier
            data (Data): data to be validated

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

    def to_json(self):
        """Export repository content as json serializable data.

        Entire repository content is exported as json serializable data.
        New repository can be created from the exported content by using
        :meth:`SchemaRepository.from_json`.

        Returns:
            Data

        """
        return self._data

    @staticmethod
    def from_json(data):
        """Create new repository from content exported as json serializable
        data.

        Creates a new repository from content of another repository that was
        exported by using :meth:`SchemaRepository.to_json`.

        Args:
            data (Data): repository data

        Returns:
            SchemaRepository

        """
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


def _monkeypatch_jsonpatch():
    """Monkeypatch jsonpatch.

    Patch incorrect value comparison between ``bool`` and numeric values when
    diffing json serializable data.

    Comparing `False` to `0` or `0.0`; and `True` to `1` or `1.0` incorrectly
    results in no change.

    """
    def _compare_values(self, path, key, src, dst):

        if isinstance(src, jsonpatch.MutableMapping) and \
                isinstance(dst, jsonpatch.MutableMapping):
            self._compare_dicts(jsonpatch._path_join(path, key), src, dst)

        elif isinstance(src, jsonpatch.MutableSequence) and \
                isinstance(dst, jsonpatch.MutableSequence):
            self._compare_lists(jsonpatch._path_join(path, key), src, dst)

        elif isinstance(src, bool) == isinstance(dst, bool) and src == dst:
            pass

        else:
            self._item_replaced(path, key, dst)

    jsonpatch.DiffBuilder._compare_values = _compare_values


_monkeypatch_jsonpatch()
