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
    | Null                  | None             |
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


class Encoder:
    """ASN1 Encoder

    Args:
        encoding (Encoding): encoding
        repository (Repository): repository

    """

    def __init__(self, encoding, repository):
        self._encoding = encoding
        self._repository = repository

    @property
    def syntax_name(self):
        """ObjectIdentifier: encoder syntax name"""
        if self._encoding == Encoding.BER:
            return ber.syntax_name
        raise ValueError('invalid encoding')

    def encode(self, module, name, value):
        """Encode value to data

        Args:
            module (str): module name
            name (str): type name
            value (Value): value

        Returns:
            Data

        """
        entity = self.encode_value(module, name, value)
        data = self.encode_entity(entity)
        return data

    def decode(self, module, name, data):
        """Decode value from data

        Args:
            module (str): module name
            name (str): type name
            data (Data): data

        Returns:
            Tuple[Value,Data]: value and remaining data

        """
        entity, rest = self.decode_entity(data)
        value = self.decode_value(module, name, entity)
        return value, rest

    def encode_value(self, module, name, value):
        """Encode value to entity

        Args:
            module (str): module name
            name (str): type name
            value (Value): value

        Returns:
            Entity

        """
        if self._encoding == Encoding.BER:
            return ber.encode_value(self._repository._refs,
                                    common.TypeRef(module, name),
                                    value)
        raise ValueError('invalid encoding')

    def decode_value(self, module, name, entity):
        """Decode value from entity

        Args:
            module (str): module name
            name (str): type name
            entity (Entity): entity

        Returns:
            Value

        """
        if self._encoding == Encoding.BER:
            return ber.decode_value(self._repository._refs,
                                    common.TypeRef(module, name),
                                    entity)
        raise ValueError('invalid encoding')

    def encode_entity(self, entity):
        """Encode entity to data

        Args:
            module (str): module name
            name (str): type name
            entity (Entity): entity

        Returns:
            Data

        """
        if self._encoding == Encoding.BER:
            return ber.encode_entity(entity)
        raise ValueError('invalid encoding')

    def decode_entity(self, data):
        """Decode entity from data

        Args:
            module (str): module name
            name (str): type name
            data (Data): data

        Returns:
            Tuple[Entity,Data]: entity and remaining data

        """
        if self._encoding == Encoding.BER:
            return ber.decode_entity(data)
        raise ValueError('invalid encoding')


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

    Args:
        args (Union[pathlib.PurePath,str,Repository]): init arguments

    """

    def __init__(self, *args):
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
    def from_json(data):
        """Create repository from JSON data representation

        Args:
            data (Union[pathlib.PurePath,json.Data]): repository data

        Returns:
            Repository

        """
        if isinstance(data, pathlib.PurePath):
            data = json.decode_file(data)
        repo = Repository()
        repo._refs = {common.type_from_json(k): common.type_from_json(v)
                      for k, v in data}
        return repo

    def to_json(self):
        """Represent repository as JSON data

        Returns:
            json.Data

        """
        return [[common.type_to_json(k), common.type_to_json(v)]
                for k, v in self._refs.items()]

    def generate_html_doc(self):
        """Generate HTML documentation

        Returns:
            str

        """
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
