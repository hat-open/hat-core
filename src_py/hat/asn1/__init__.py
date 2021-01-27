"""Abstract Syntax Notation One

Value mapping:

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

"""

import enum
import pathlib
import typing

from hat import json
from hat.asn1 import ber
from hat.asn1 import common
from hat.asn1 import doc
from hat.asn1.common import (Data,
                             Value,
                             Boolean,
                             Integer,
                             BitString,
                             OctetString,
                             Null,
                             ObjectIdentifier,
                             String,
                             External,
                             Real,
                             Enumerated,
                             EmbeddedPDV,
                             Choice,
                             Set,
                             SetOf,
                             Sequence,
                             SequenceOf,
                             Entity,
                             is_oid_eq)


__all__ = ['Data',
           'Value',
           'Boolean',
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
           'Entity',
           'is_oid_eq',
           'Encoding',
           'Encoder',
           'Repository']


Encoding = enum.Enum('Encoding', ['BER'])


class Repository:
    """ASN.1 type definition repository.

    Repository can be initialized with multiple arguments, which can be
    instances of ``pathlib.PurePath``, ``str`` or ``Repository``.

    If an argument is of type ``pathlib.PurePath``, and path points to file
    with a suffix '.asn', ASN.1 type definitions are decoded from the file.
    Otherwise, it is assumed that path points to a directory,
    which is recursively searched for ASN.1 definitions. All decoded types
    are added to the repository. Previously added type definitions with the
    same references are replaced.

    If an argument is of type ``str``, it represents ASN.1 type definitions.
    All decoded types are added to the repository. Previously added type
    definitions with the same references are replaced.

    If an argument is of type ``Repository``, its data definitions are added to
    the new repository. Previously added type definitions with the
    same references are replaced.

    """

    def __init__(self, *args: typing.Union[pathlib.PurePath,
                                           str,
                                           'Repository']):
        self._refs = {}
        for arg in args:
            if isinstance(arg, pathlib.PurePath):
                self._load_path(arg)
            elif isinstance(arg, str):
                self._parse_asn1_def(arg)
            elif isinstance(arg, Repository):
                self._refs.update(arg._refs)
            else:
                raise ValueError('invalid argument')

    @staticmethod
    def from_json(data: typing.Union[pathlib.PurePath, json.Data]
                  ) -> 'Repository':
        """Create repository from JSON data representation"""
        if isinstance(data, pathlib.PurePath):
            data = json.decode_file(data)
        repo = Repository()
        repo._refs = {common.type_from_json(k): common.type_from_json(v)
                      for k, v in data}
        return repo

    def to_json(self) -> json.Data:
        """Represent repository as JSON data"""
        return [[common.type_to_json(k), common.type_to_json(v)]
                for k, v in self._refs.items()]

    def generate_html_doc(self) -> str:
        """Generate HTML documentation"""
        return doc.generate_html(self._refs)

    def _load_path(self, path):
        paths = [path] if path.suffix == '.asn' else path.rglob('*.asn')
        for path in paths:
            with open(path, 'r', encoding='utf-8') as f:
                asn1_def = f.read()
            self._parse_asn1_def(asn1_def)

    def _parse_asn1_def(self, asn1_def):
        from hat.asn1 import parser
        refs = parser.parse(asn1_def)
        self._refs.update(refs)


class Encoder:
    """ASN1 Encoder"""

    def __init__(self,
                 encoding: Encoding,
                 repository: Repository):
        self._encoding = encoding
        self._repository = repository

    @property
    def syntax_name(self) -> ObjectIdentifier:
        """Encoder syntax name"""
        if self._encoding == Encoding.BER:
            return ber.syntax_name
        raise ValueError('invalid encoding')

    def encode(self,
               module: str,
               name: str,
               value: Value
               ) -> Data:
        """Encode value to data"""
        entity = self.encode_value(module, name, value)
        data = self.encode_entity(entity)
        return data

    def decode(self,
               module: str,
               name: str,
               data: Data
               ) -> typing.Tuple[Value, Data]:
        """Decode value from data

        Returns value and remaining data.

        """
        entity, rest = self.decode_entity(data)
        value = self.decode_value(module, name, entity)
        return value, rest

    def encode_value(self,
                     module: str,
                     name: str,
                     value: Value
                     ) -> Entity:
        """Encode value to entity"""
        if self._encoding == Encoding.BER:
            return ber.encode_value(self._repository._refs,
                                    common.TypeRef(module, name),
                                    value)
        raise ValueError('invalid encoding')

    def decode_value(self,
                     module: str,
                     name: str,
                     entity: Entity
                     ) -> Value:
        """Decode value from entity"""
        if self._encoding == Encoding.BER:
            return ber.decode_value(self._repository._refs,
                                    common.TypeRef(module, name),
                                    entity)
        raise ValueError('invalid encoding')

    def encode_entity(self,
                      entity: Entity
                      ) -> Data:
        """Encode entity to data"""
        if self._encoding == Encoding.BER:
            return ber.encode_entity(entity)
        raise ValueError('invalid encoding')

    def decode_entity(self,
                      data: Data
                      ) -> typing.Tuple[Entity, Data]:
        """Decode entity from data

        Returns entity and remaining data.

        """
        if self._encoding == Encoding.BER:
            return ber.decode_entity(data)
        raise ValueError('invalid encoding')
