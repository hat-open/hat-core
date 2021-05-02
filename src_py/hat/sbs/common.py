import typing

from hat import util


class Ref(typing.NamedTuple):
    module: typing.Optional[str]
    name: str


class BooleanType(typing.NamedTuple):
    pass


class IntegerType(typing.NamedTuple):
    pass


class FloatType(typing.NamedTuple):
    pass


class StringType(typing.NamedTuple):
    pass


class BytesType(typing.NamedTuple):
    pass


class ArrayType(typing.NamedTuple):
    t: 'Type'


class TupleType(typing.NamedTuple):
    entries: typing.List[typing.Tuple[str, 'Type']]


class UnionType(typing.NamedTuple):
    entries: typing.List[typing.Tuple[str, 'Type']]


Type = typing.Union[Ref,
                    BooleanType,
                    IntegerType,
                    FloatType,
                    StringType,
                    BytesType,
                    ArrayType,
                    TupleType,
                    UnionType]
util.register_type_alias('Type')

Data = typing.Union[bool, int, float, str, bytes,
                    typing.List['Data'],
                    typing.Dict[str, 'Data'],
                    typing.Tuple[str, 'Data']]
util.register_type_alias('Data')
