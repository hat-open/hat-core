import abc
import typing

from hat.sbs import common
from hat.sbs import _pyserializer

try:
    from hat.sbs import _cserializer
except ImportError:
    _cserializer = None


class Serializer(abc.ABC):

    @staticmethod
    @abc.abstractmethod
    def encode(refs: typing.Dict[common.Ref, common.Type],
               t: common.Type,
               value: common.Data
               ) -> bytes:
        """Encode value"""

    @staticmethod
    @abc.abstractmethod
    def decode(refs: typing.Dict[common.Ref, common.Type],
               t: common.Type,
               data: memoryview
               ) -> common.Data:
        """Decode data"""


class CSerializer(Serializer):
    """Serializer implementation in C"""

    def encode(refs, t, value):
        if not _cserializer:
            raise Exception('implementation not available')
        return _cserializer.encode(refs, t, value)

    def decode(refs, t, data):
        if not _cserializer:
            raise Exception('implementation not available')
        return _cserializer.decode(refs, t, data)


class PySerializer(Serializer):
    """Serializer implementation in Python"""

    def encode(refs, t, value):
        return _pyserializer.encode(refs, t, value)

    def decode(refs, t, data):
        return _pyserializer.decode(refs, t, data)
