import typing

from hat.sbs import common

try:
    from hat.sbs import _cserializer as _serializer
except Exception:
    from hat.sbs import _pyserializer as _serializer


def encode(refs: typing.Dict[common.Ref, common.Type],
           t: common.Type,
           value: common.Data
           ) -> bytes:
    """Encode value.

    Args:
        refs: type references
        t: SBS type
        value: value

    """
    return _serializer.encode(refs, t, value)


def decode(refs: typing.Dict[common.Ref, common.Type],
           t: common.Type,
           data: memoryview
           ) -> typing.Tuple[common.Data, memoryview]:
    """Decode data.

    Args:
        refs: type references
        t: SBS type
        data: data

    """
    return _serializer.decode(refs, t, data)
