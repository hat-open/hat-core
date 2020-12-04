import abc
import enum
import typing

from hat import util


class ClassType(enum.Enum):
    UNIVERSAL = 0
    APPLICATION = 1
    CONTEXT_SPECIFIC = 2
    PRIVATE = 3


TypeProperty = util.namedtuple(
    'TypeProperty',
    ['name', 'str'],
    ['type', 'Type'],
    ['optional', 'bool', False])


TypeRef = util.namedtuple(
    'TypeRef',
    ['module', 'str: module name'],
    ['name', 'str: type name'])


Type = typing.Union[TypeRef,
                    'BooleanType',
                    'IntegerType',
                    'BitStringType',
                    'OctetStringType',
                    'NullType',
                    'ObjectIdentifierType',
                    'StringType',
                    'ExternalType',
                    'RealType',
                    'EnumeratedType',
                    'EmbeddedPDVType',
                    'ChoiceType',
                    'SetType',
                    'SetOfType',
                    'SequenceType',
                    'SequenceOfType',
                    'EntityType',
                    'UnsupportedType',
                    'PrefixedType']
"""Type"""


BooleanType = util.namedtuple('BooleanType')


IntegerType = util.namedtuple('IntegerType')


BitStringType = util.namedtuple('BitStringType')


OctetStringType = util.namedtuple('OctetStringType')


NullType = util.namedtuple('NullType')


ObjectIdentifierType = util.namedtuple('ObjectIdentifierType')


class StringType(enum.Enum):
    ObjectDescriptor = 7
    UTF8String = 12
    NumericString = 18
    PrintableString = 19
    T61String = 20
    VideotexString = 21
    IA5String = 22
    UTCTime = 23
    GeneralizedTime = 24
    GraphicString = 25
    VisibleString = 26
    GeneralString = 27
    UniversalString = 28
    CHARACTER_STRING = 29
    BMPString = 30


ExternalType = util.namedtuple('ExternalType')


RealType = util.namedtuple('RealType')


EnumeratedType = util.namedtuple('EnumeratedType')


EmbeddedPDVType = util.namedtuple('EmbeddedPDVType')


ChoiceType = util.namedtuple(
    'ChoiceType',
    ['choices', 'List[TypeProperty]'])


SetType = util.namedtuple(
    'SetType',
    ['elements', 'List[TypeProperty]'])


SetOfType = util.namedtuple(
    'SetOfType',
    ['type', "Type: elements type definition"])


SequenceType = util.namedtuple(
    'SequenceType',
    ['elements', 'List[TypeProperty]'])


SequenceOfType = util.namedtuple(
    'SequenceOfType',
    ['type', "Type: elements type definition"])


EntityType = util.namedtuple('EntityType')


UnsupportedType = util.namedtuple('UnsupportedType')


PrefixedType = util.namedtuple(
    'PrefixedType',
    ['type', 'Type'],
    ['class_type', 'ClassType'],
    ['tag_number', 'int'],
    ['implicit', 'bool'])


Data = typing.Union[bytes, bytearray, memoryview]
"""Data"""


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
"""Value"""


Boolean = bool
"""Boolean"""


Integer = int
"""Integer"""


BitString = typing.List[bool]
"""Bit string"""


OctetString = bytes
"""Octet string"""


Null = None
"""Null"""


ObjectIdentifier = typing.List[typing.Union[int, typing.Tuple[str, int]]]
"""Object identifier"""


String = str
"""String"""


External = util.namedtuple(
    'External',
    ['data', 'Union[Entity,Data,List[bool]]'],
    ['direct_ref', 'Optional[ObjectIdentifier]'],
    ['indirect_ref', 'Optional[int]'])


Real = float
"""Real"""


Enumerated = int
"""Enumerated"""

# TODO: if abstract is ObjectIdentifier then transfer must be defined
EmbeddedPDV = util.namedtuple(
    'EmbeddedPDV',
    ['abstract', 'Optional[Union[int,ObjectIdentifier]]'],
    ['transfer', 'Optional[ObjectIdentifier]'],
    ['data', 'Data'])


Choice = typing.Tuple[str, Value]
"""Choice"""


Set = typing.Dict[str, Value]
"""Set"""


SetOf = typing.Iterable[Value]
"""Set of"""


Sequence = typing.Dict[str, Value]
"""Sequence"""


SequenceOf = typing.List[Value]
"""Sequence of"""


class Entity(abc.ABC):
    """Encoding independent ASN.1 Entity"""


def is_oid_eq(x, y):
    """Check if two ASN.1 object identifiers are equal

    Args:
        x (ObjectIdentifier): object identifier
        y (ObjectIdentifier): object identifier

    Returns:
        bool

    """
    if len(x) != len(y):
        return False
    for i, j in zip(x, y):
        i_id = i if isinstance(i, int) else i[1]
        j_id = j if isinstance(j, int) else j[1]
        if i_id != j_id:
            return False
    return True


def type_to_json(t):
    """Convert type definition to JSON data

    Args:
        t (Type): type

    Returns:
        hat.json.Data

    """
    if isinstance(t, TypeRef):
        return ['TypeRef', t.module, t.name]

    if isinstance(t, BooleanType):
        return ['BooleanType']

    if isinstance(t, IntegerType):
        return ['IntegerType']

    if isinstance(t, BitStringType):
        return ['BitStringType']

    if isinstance(t, OctetStringType):
        return ['OctetStringType']

    if isinstance(t, ObjectIdentifierType):
        return ['ObjectIdentifierType']

    if isinstance(t, NullType):
        return ['NullType']

    if isinstance(t, StringType):
        return ['StringType', t.name]

    if isinstance(t, ExternalType):
        return ['ExternalType']

    if isinstance(t, RealType):
        return ['RealType']

    if isinstance(t, EnumeratedType):
        return ['EnumeratedType']

    if isinstance(t, EmbeddedPDVType):
        return ['EmbeddedPDVType']

    if isinstance(t, ChoiceType):
        return ['ChoiceType', [[i.name, type_to_json(i.type)]
                               for i in t.choices]]

    if isinstance(t, SetType):
        return ['SetType', [[i.name, type_to_json(i.type), i.optional]
                            for i in t.elements]]

    if isinstance(t, SetOfType):
        return ['SetOfType', type_to_json(t.type)]

    if isinstance(t, SequenceType):
        return ['SequenceType', [[i.name, type_to_json(i.type), i.optional]
                                 for i in t.elements]]

    if isinstance(t, SequenceOfType):
        return ['SequenceOfType', type_to_json(t.type)]

    if isinstance(t, EntityType):
        return ['EntityType']

    if isinstance(t, UnsupportedType):
        return ['UnsupportedType']

    if isinstance(t, PrefixedType):
        return ['PrefixedType', type_to_json(t.type), t.class_type.name,
                t.tag_number, t.implicit]

    raise ValueError('invalid type definition')


def type_from_json(data):
    """Convert JSON data to type definition

    Args:
        data (hat.json.Data): data

    Returns:
        Type

    """
    if data[0] == 'TypeRef':
        return TypeRef(module=data[1],
                       name=data[2])

    if data[0] == 'BooleanType':
        return BooleanType()

    if data[0] == 'IntegerType':
        return IntegerType()

    if data[0] == 'BitStringType':
        return BitStringType()

    if data[0] == 'OctetStringType':
        return OctetStringType()

    if data[0] == 'NullType':
        return NullType()

    if data[0] == 'ObjectIdentifierType':
        return ObjectIdentifierType()

    if data[0] == 'StringType':
        return StringType[data[1]]

    if data[0] == 'ExternalType':
        return ExternalType()

    if data[0] == 'RealType':
        return RealType()

    if data[0] == 'EnumeratedType':
        return EnumeratedType()

    if data[0] == 'EmbeddedPDVType':
        return EmbeddedPDVType()

    if data[0] == 'ChoiceType':
        return ChoiceType([TypeProperty(name=i[0],
                                        type=type_from_json(i[1]))
                           for i in data[1]])

    if data[0] == 'SetType':
        return SetType([TypeProperty(name=i[0],
                                     type=type_from_json(i[1]),
                                     optional=i[2])
                        for i in data[1]])

    if data[0] == 'SetOfType':
        return SetOfType(type_from_json(data[1]))

    if data[0] == 'SequenceType':
        return SequenceType([TypeProperty(name=i[0],
                                          type=type_from_json(i[1]),
                                          optional=i[2])
                             for i in data[1]])

    if data[0] == 'SequenceOfType':
        return SequenceOfType(type_from_json(data[1]))

    if data[0] == 'EntityType':
        return EntityType()

    if data[0] == 'UnsupportedType':
        return UnsupportedType()

    if data[0] == 'PrefixedType':
        return PrefixedType(type=type_from_json(data[1]),
                            class_type=ClassType[data[2]],
                            tag_number=data[3],
                            implicit=data[4])

    raise ValueError('invalid data')
