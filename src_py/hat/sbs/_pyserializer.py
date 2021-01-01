import collections
import itertools
import struct
import typing

from hat.sbs import common


def encode(refs: typing.Dict[common.Ref, common.Type],
           t: common.Type,
           value: common.Data
           ) -> bytes:
    return _encode_generic(refs, t, value)


def decode(refs: typing.Dict[common.Ref, common.Type],
           t: common.Type,
           data: memoryview
           ) -> common.Data:
    data, _ = _decode_generic(refs, t, data)
    return data


def _encode_generic(refs, t, value):
    while isinstance(t, common.Ref) and t in refs:
        t = refs[t]
    if isinstance(t, common.BooleanType):
        return _encode_Boolean(value)
    if isinstance(t, common.IntegerType):
        return _encode_Integer(value)
    if isinstance(t, common.FloatType):
        return _encode_Float(value)
    if isinstance(t, common.StringType):
        return _encode_String(value)
    if isinstance(t, common.BytesType):
        return _encode_Bytes(value)
    if isinstance(t, common.ArrayType):
        return _encode_Array(refs, t, value)
    if isinstance(t, common.TupleType):
        return _encode_Tuple(refs, t, value)
    if isinstance(t, common.UnionType):
        return _encode_Union(refs, t, value)
    raise ValueError()


def _decode_generic(refs, t, data):
    while isinstance(t, common.Ref) and t in refs:
        t = refs[t]
    if isinstance(t, common.BooleanType):
        return _decode_Boolean(data)
    if isinstance(t, common.IntegerType):
        return _decode_Integer(data)
    if isinstance(t, common.FloatType):
        return _decode_Float(data)
    if isinstance(t, common.StringType):
        return _decode_String(data)
    if isinstance(t, common.BytesType):
        return _decode_Bytes(data)
    if isinstance(t, common.ArrayType):
        return _decode_Array(refs, t, data)
    if isinstance(t, common.TupleType):
        return _decode_Tuple(refs, t, data)
    if isinstance(t, common.UnionType):
        return _decode_Union(refs, t, data)
    raise ValueError()


def _encode_Boolean(value):
    return b'\x01' if value else b'\x00'


def _decode_Boolean(data):
    return bool(data[0]), data[1:]


def _encode_Integer(value):
    ret = collections.deque()
    while True:
        temp = value & 0x7F
        if not ret:
            temp |= 0x80
        ret.appendleft(temp)
        value = value >> 7
        if value == 0 and not (temp & 0x40):
            break
        if value == -1 and (temp & 0x40):
            break
    return bytes(ret)


def _decode_Integer(data):
    ret = -1 if data[0] & 0x40 else 0
    while True:
        ret = (ret << 7) | (data[0] & 0x7F)
        if data[0] & 0x80:
            return ret, data[1:]
        data = data[1:]


def _encode_Float(value):
    return struct.pack('>d', value)


def _decode_Float(data):
    return struct.unpack('>d', data[:8])[0], data[8:]


def _encode_String(value):
    ret = value.encode('utf-8')
    return _encode_Integer(len(ret)) + ret


def _decode_String(data):
    bytes_len, data = _decode_Integer(data)
    return str(data[:bytes_len], encoding='utf-8'), data[bytes_len:]


def _encode_Bytes(value):
    return _encode_Integer(len(value)) + value


def _decode_Bytes(data):
    bytes_len, data = _decode_Integer(data)
    return data[:bytes_len], data[bytes_len:]


def _encode_Array(refs, t, value):
    return bytes(itertools.chain(
        _encode_Integer(len(value)),
        itertools.chain.from_iterable(
            _encode_generic(refs, t.t, i) for i in value)))


def _decode_Array(refs, t, data):
    count, data = _decode_Integer(data)
    ret = collections.deque()
    for _ in range(count):
        i, data = _decode_generic(refs, t.t, data)
        ret.append(i)
    return list(ret), data


def _encode_Tuple(refs, t, value):
    if not t.entries:
        return b''
    return bytes(itertools.chain.from_iterable(
        _encode_generic(refs, entry_type, value[entry_name])
        for entry_name, entry_type in t.entries))


def _decode_Tuple(refs, t, data):
    if not t.entries:
        return None, data
    ret = {}
    for entry_name, entry_type in t.entries:
        ret[entry_name], data = _decode_generic(refs, entry_type, data)
    return ret, data


def _encode_Union(refs, t, value):
    if not t.entries:
        return b''
    for i, (entry_name, entry_type) in enumerate(t.entries):
        if entry_name == value[0]:
            break
    else:
        raise Exception()
    return bytes(itertools.chain(
        _encode_Integer(i),
        _encode_generic(refs, entry_type, value[1])))


def _decode_Union(refs, t, data):
    if not t.entries:
        return None, data
    i, data = _decode_Integer(data)
    entry_name, entry_type = t.entries[i]
    value, data = _decode_generic(refs, entry_type, data)
    return (entry_name, value), data
