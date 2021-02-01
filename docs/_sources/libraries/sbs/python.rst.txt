.. _hat-sbs:

`hat.sbs` - Python simple binary serialization library
======================================================

This library provides Python implementation of :ref:`SBS <sbs>` parser and
data serializer.


Python data types
-----------------

Translation between SBS types and Python types is done according to following
translation table:

    +----------+------------------+
    | SBS type | Python type      |
    +==========+==================+
    | Boolean  | bool             |
    +----------+------------------+
    | Integer  | int              |
    +----------+------------------+
    | Float    | float            |
    +----------+------------------+
    | String   | str              |
    +----------+------------------+
    | Bytes    | bytes            |
    +----------+------------------+
    | Array    | List[Data]       |
    +----------+------------------+
    | Tuple    | Dict[str, Data]  |
    +----------+------------------+
    | Union    | Tuple[str, Data] |
    +----------+------------------+

SBS Tuple and Union types without elements are translated to ``None``.

`hat.sbs` provides data type definition as::

    Data = typing.Union[bool, int, float, str, bytes,
                        typing.List['Data'],
                        typing.Dict[str, 'Data'],
                        typing.Tuple[str, 'Data']]


.. _hat-sbs-Repository:

Repository
----------

`hat.sbs.Repository` is used as collection of interconnected SBS schemas.
Instance of `Repository` can be represented as JSON data enabling efficient
storage and reconstruction of SBS repositories.

Once `Repository` instance is initialized, methods `encode` and `decode`
are used for SBS data serialization.

During initialization, `Repository` accepts arbitrary implementation
of SBS serializer. `hat.sbs` provides these serializer implementations:

    * `hat.sbs.CSerializer` (default)

        SBS serializer implemented as C extension.

    * `hat.sbs.PySerializer`

        Pure Python implementation of SBS serializer.

::

    class Repository:

        def __init__(self,
                     *args: typing.Union['Repository', pathlib.Path, str],
                     serializer=serializer.CSerializer): ...

        def encode(self,
                   module_name: typing.Optional[str],
                   type_name: str,
                   value: common.Data
                   ) -> bytes: ...

        def decode(self,
                   module_name: typing.Optional[str],
                   type_name: str,
                   data: typing.Union[bytes, bytearray, memoryview]
                   ) -> common.Data: ...

        def to_json(self) -> json.Data: ...

        @staticmethod
        def from_json(data: typing.Union[pathlib.PurePath, common.Data],
                      *,
                      serializer=serializer.CSerializer
                      ) -> 'Repository': ...

Example usage::

    import hat.sbs

    repo = hat.sbs.Repository('''
        module Module

        Entry(K, V) = Tuple {
            key: K
            value: V
        }

        T = Array(Maybe(Entry(String, Integer)))
    ''')
    data = [
        ('Nothing', None),
        ('Just', {
            'key': 'abc',
            'value': 123
        })
    ]
    encoded_data = repo.encode('Module', 'T', data)
    decoded_data = repo.decode('Module', 'T', encoded_data)
    assert data == decoded_data


API
---

API reference is available as part of generated documentation:

    * `Python hat.sbs module <../../pyhat/hat/sbs/index.html>`_
