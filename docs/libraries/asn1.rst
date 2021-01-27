.. _hat-asn1:

`hat.asn1` - Python Abstract Syntax Notation One library
========================================================

This library provides implementation of
`ASN.1 <https://en.wikipedia.org/wiki/ASN.1>`_ schema parser and
`BER <https://en.wikipedia.org/wiki/X.690#BER_encoding>`_ encoder/decoder.
Additionally, HTML documentation of parsed ASN.1 schemas can be generated.


Python data mappings
--------------------

Mapping between ASN.1 data types and built in types:

    +-----------------------+------------------+
    | ASN.1 type            | Python type      |
    +=======================+==================+
    | Boolean               | bool             |
    +-----------------------+------------------+
    | Integer               | int              |
    +-----------------------+------------------+
    | BitString             | List[bool]       |
    +-----------------------+------------------+
    | OctetString           | bytes            |
    +-----------------------+------------------+
    | Null                  | ``None``         |
    +-----------------------+------------------+
    | ObjectIdentifier      | List[int]        |
    +-----------------------+------------------+
    | String                | str              |
    +-----------------------+------------------+
    | External              | External         |
    +-----------------------+------------------+
    | Real                  | float            |
    +-----------------------+------------------+
    | Enumerated            | int              |
    +-----------------------+------------------+
    | EmbeddedPDV           | EmbeddedPDV      |
    +-----------------------+------------------+
    | Choice                | Tuple[str,Value] |
    +-----------------------+------------------+
    | Set                   | Dict[str,Value]  |
    +-----------------------+------------------+
    | SetOf                 | Iterable[Value]  |
    +-----------------------+------------------+
    | Sequence              | Dict[str,Value]  |
    +-----------------------+------------------+
    | SequenceOf            | List[Value]      |
    +-----------------------+------------------+
    | ABSTRACT-SYNTAX.&Type | Entity           |
    +-----------------------+------------------+

For Choice, Set and Sequence, `str` represents field name.

According to previous mapping, this library defines following types::

    Data = typing.Union[bytes, bytearray, memoryview]

    Value = typing.Union['Boolean',
                         'Integer',
                         'BitString',
                         'OctetString',
                         'Null',
                         'ObjectIdentifier',
                         'String',
                         'External',
                         'Real',
                         'Enumerated',
                         'EmbeddedPDV',
                         'Choice',
                         'Set',
                         'SetOf',
                         'Sequence',
                         'SequenceOf',
                         'Entity']

    Boolean = bool
    Integer = int
    BitString = typing.List[bool]
    OctetString = bytes
    Null = None
    ObjectIdentifier = typing.List[typing.Union[int, typing.Tuple[str, int]]]
    String = str
    Real = float
    Enumerated = int
    Choice = typing.Tuple[str, Value]
    Set = typing.Dict[str, Value]
    SetOf = typing.Iterable[Value]
    Sequence = typing.Dict[str, Value]
    SequenceOf = typing.List[Value]

    class External(typing.NamedTuple):
        data: typing.Union['Entity', Data, typing.List[bool]]
        direct_ref: typing.Optional[ObjectIdentifier]
        indirect_ref: typing.Optional[int]

    class EmbeddedPDV(typing.NamedTuple):
        abstract: typing.Optional[typing.Union[int, ObjectIdentifier]]
        transfer: typing.Optional[ObjectIdentifier]
        data: Data

    class Entity(abc.ABC):
        """Encoding independent ASN.1 Entity"""


.. _hat-asn1-Repository:

Repository
----------

`hat.asn1.Repository` is used as parser of ASN.1 schemas. ASN.1 data definition
is parsed during `Repository` instance initialization. These definitions
are required for encoding/decoding ASN.1 data. Instance of `Repository` can be
represented as JSON data enabling efficient storage and reconstruction of ASN.1
repositories without repetitive parsing of ASN.1 schemas.

::

    class Repository:

        def __init__(self, *args: typing.Union[pathlib.PurePath,
                                               str,
                                               'Repository']): ...

        @staticmethod
        def from_json(data: typing.Union[pathlib.PurePath, json.Data]
                      ) -> 'Repository': ...

        def to_json(self) -> json.Data: ...

        def generate_html_doc(self) -> str: ...

Once instance of `Repository` is created, HTML documentation describing
data structures can be generated with `generate_html_doc` method (example
of `generated documentation <../../asn1/doc.html>`_).


.. _hat-asn1-Encoder:

Encoder
-------

`hat.asn1.Encoder` provides interface for encoding/decoding ASN.1 data
based on ASN.1 data definitions parsed by `hat.asn1.Repository`::

    Encoding = enum.Enum('Encoding', ['BER'])

    class Encoder:

        def __init__(self,
                     encoding: Encoding,
                     repository: Repository): ...

        @property
        def syntax_name(self) -> ObjectIdentifier: ...

        def encode(self,
                   module: str,
                   name: str,
                   value: Value
                   ) -> Data: ...

        def decode(self,
                   module: str,
                   name: str,
                   data: Data
                   ) -> typing.Tuple[Value, Data]: ...

        def encode_value(self,
                         module: str,
                         name: str,
                         value: Value
                         ) -> Entity: ...

        def decode_value(self,
                         module: str,
                         name: str,
                         entity: Entity
                         ) -> Value: ...

        def encode_entity(self,
                          entity: Entity
                          ) -> Data: ...

        def decode_entity(self,
                          data: Data
                          ) -> typing.Tuple[Entity, Data]: ...


Example
-------

::

    repo = asn1.Repository(r"""
        Example DEFINITIONS ::= BEGIN
            T ::= SEQUENCE OF CHOICE {
                a BOOLEAN,
                b INTEGER,
                c UTF8String
            }
        END
    """)

    encoder = asn1.Encoder(asn1.Encoding.BER, repo)

    value = [('c', '123'), ('a', True), ('a', False), ('b', 123)]

    encoded = encoder.encode('Example', 'T', value)
    decoded, rest = encoder.decode('Example', 'T', encoded)

    assert value == decoded
    assert len(rest) == 0


API
---

API reference is available as part of generated documentation:

    * `Python hat.asn1 module <../pyhat/hat/asn1/index.html>`_
