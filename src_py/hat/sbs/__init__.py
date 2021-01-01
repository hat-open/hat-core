"""Simple binary serializer

This implementation of SBS encoder/decoder translates between SBS types and
Python types according to following translation table:

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

Example usage of SBS serializer::

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

"""

from hat.sbs.common import Data
from hat.sbs.repository import Repository
from hat.sbs.serializer import (Serializer,
                                CSerializer,
                                PySerializer)


__all__ = ['Repository', 'Data', 'Serializer', 'CSerializer', 'PySerializer']
