import pathlib
import typing

from hat.sbs import evaluator
from hat.sbs import parser
from hat.sbs import serializer
from hat.util import json


class Repository:
    """SBS schema repository.

    Supported initialization arguments:
        * string containing sbs schema
        * file path to .sbs file
        * path to direcory recursivly searched for .sbs files
        * other repository

    """

    def __init__(self, *args: typing.Union['Repository', pathlib.Path, str]):
        self._modules = list(_parse_args(args))
        self._refs = evaluator.evaluate_modules(self._modules)

    def encode(self,
               module_name: typing.Optional[str],
               type_name: str,
               value: serializer.Data
               ) -> bytes:
        """Encode value."""
        ref = serializer.Ref(module_name, type_name)
        return serializer.encode(self._refs, ref, value)

    def decode(self,
               module_name: typing.Optional[str],
               type_name: str,
               data: typing.Union[bytes, bytearray, memoryview]
               ) -> serializer.Data:
        """Decode data."""
        ref = serializer.Ref(module_name, type_name)
        return serializer.decode(self._refs, ref, memoryview(data))[0]

    def to_json(self) -> json.Data:
        """Export repository content as json serializable data.

        Entire repository content is exported as json serializable data.
        New repository can be created from the exported content by using
        :meth:`Repository.from_json`.

        """
        return [parser.module_to_json(module) for module in self._modules]

    @staticmethod
    def from_json(data: typing.Union[pathlib.PurePath, serializer.Data]
                  ) -> 'Repository':
        """Create new repository from content exported as json serializable
        data.

        Creates a new repository from content of another repository that was
        exported by using :meth:`Repository.to_json`.

        """
        if isinstance(data, pathlib.PurePath):
            data = json.decode_file(data)
        repo = Repository()
        repo._modules = [parser.module_from_json(i) for i in data]
        repo._refs = evaluator.evaluate_modules(repo._modules)
        return repo


def _parse_args(args):
    for arg in args:
        if isinstance(arg, pathlib.PurePath):
            paths = ([arg] if arg.suffix == '.sbs'
                     else arg.rglob('*.sbs'))
            for path in paths:
                with open(path, encoding='utf-8') as f:
                    yield parser.parse(f.read())
        elif isinstance(arg, Repository):
            yield from arg._modules
        elif isinstance(arg, str):
            yield parser.parse(arg)
        else:
            raise ValueError()
