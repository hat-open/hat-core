Hat Core - Python JSON library
==============================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-json` documentation - `<https://core.hat-open.com/docs/libraries/json.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

JSON data manipulation and validation functions.

* type definitions::

    Array: typing.Type = typing.List['Data']
    Object: typing.Type = typing.Dict[str, 'Data']
    Data: typing.Type = typing.Union[None, bool, int, float, str, Array, Object]
    """JSON data type identifier."""

    Format = enum.Enum('Format', ['JSON', 'YAML'])
    """Encoding format"""

    Path: typing.Type = typing.Union[int, str, typing.List['Path']]
    """Data path"""


* `hat.json.equals` and `hat.json.flatten`::

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

    def flatten(data: Data
                ) -> typing.Iterable[Data]:
        """Flatten JSON data

        If `data` is array, this generator recursively yields result of
        `flatten` call with each element of input list. For other `Data` types,
        input data is yielded.

        Example::

            data = [1, [], [2], {'a': [3]}]
            result = [1, 2, {'a': [3]}]
            assert list(flatten(data)) == result

        """


* `hat.json.get` and `hat.json.set_`::

    def get(data: Data,
            path: Path
            ) -> Data:
        """Get data element referenced by path

        Example::

            data = {'a': [1, 2, [3, 4]]}
            path = ['a', 2, 0]
            assert get(data, path) == 3

            data = [1, 2, 3]
            assert get(data, 0) == 1
            assert get(data, 5) is None

        """

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


* `hat.json.diff` and `hat.json.patch`::

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


* `hat.json.encode` and `hat.json.decode`::

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

    def decode(data_str: str,
               format: Format = Format.JSON
               ) -> Data:
        """Decode JSON data.

        Args:
            data_str: encoded JSON data
            format: encoding format

        """


* `hat.json.encode_file` and `hat.json.decode_file`::

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

    def decode_file(path: pathlib.PurePath,
                    format: typing.Optional[Format] = None
                    ) -> Data:
        """Decode JSON data from file.

        If `format` is ``None``, encoding format is derived from path suffix.

        Args:
            path: file path
            format: encoding format

        """


* `hat.json.SchemaRepository`::

    class SchemaRepository:
        """JSON Schema repository.

        A repository that holds json schemas and enables validation against
        them.

        Repository can be initialized with multiple arguments, which can be
        instances of ``pathlib.PurePath``, ``Data`` or ``SchemaRepository``.

        If an argument is of type ``pathlib.PurePath``, and path points to file
        with a suffix '.json', '.yml' or '.yaml', json serializable data is
        decoded from the file. Otherwise, it is assumed that path points to a
        directory, which is recursively searched for json and yaml files. All
        decoded schemas are added to the repository. If a schema with the same
        `id` was previosly added, an exception is raised.

        If an argument is of type ``Data``, it should be a json serializable
        data representation of a JSON schema. If a schema with the same `id`
        was previosly added, an exception is raised.

        If an argument is of type ``SchemaRepository``, its schemas are added
        to the new repository. Previously added schemas with the same `id` are
        replaced.

        """

        def __init__(self, *args: typing.Union[pathlib.PurePath,
                                               Data,
                                               'SchemaRepository']): ...

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

        def to_json(self) -> Data:
            """Export repository content as json serializable data.

            Entire repository content is exported as json serializable data.
            New repository can be created from the exported content by using
            :meth:`SchemaRepository.from_json`.

            """

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
