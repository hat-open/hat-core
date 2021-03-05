"""Implementation of blessing calculation algorithms"""

import enum
import typing

from hat.monitor.server import common


Algorithm = enum.Enum('Algorithm', [
    'BLESS_ALL',
    'BLESS_ONE'])


_last_token_id = 0


def calculate(components: typing.List[common.ComponentInfo],
              group_algorithms: typing.Dict[str, Algorithm],
              default_algorithm: Algorithm
              ) -> typing.List[common.ComponentInfo]:
    """Calculate blessing

    Args:
        components: components state with previous blessing tokens
        group_algorithms: association of algorithm to group
        default_algorithm: default algorithm

    Returns:
        components state with updated blessing

    """
    group_components = {}
    for c in components:
        group_components.setdefault(c.group, []).append(c)

    blessings = {}
    for group, components_from_group in group_components.items():
        algorithm = group_algorithms.get(group, default_algorithm)
        for c in _calculate_group(algorithm, components_from_group):
            blessings[c.mid, c.cid] = c.blessing

    return [c._replace(blessing=blessings[c.mid, c.cid])
            for c in components]


def _calculate_group(algorithm, components):
    if algorithm == Algorithm.BLESS_ALL:
        return _bless_all(components)

    if algorithm == Algorithm.BLESS_ONE:
        return _bless_one(components)

    raise ValueError('unsupported algorithm')


def _bless_all(components):
    global _last_token_id

    for c in components:
        if c.blessing is not None:
            yield c

        else:
            _last_token_id += 1
            yield c._replace(blessing=_last_token_id)


def _bless_one(components):
    global _last_token_id

    highlander = None
    ready_exist = False
    for c in components:
        if c.ready:
            ready_exist = True
        if c.ready == 0:
            continue
        if highlander and highlander.rank < c.rank:
            continue
        if highlander and highlander.rank == c.rank and (highlander.blessing or
                                                         not c.blessing):
            continue
        highlander = c

    if highlander and not highlander.blessing and ready_exist:
        highlander = None

    for c in components:
        if c != highlander:
            c = c._replace(blessing=None)
        elif not c.blessing:
            _last_token_id += 1
            c = c._replace(blessing=_last_token_id)
        yield c
