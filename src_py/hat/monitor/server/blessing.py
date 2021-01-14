"""Implementation of blessing calculation algorithms"""

import enum
import typing

from hat import util
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
    if not components:
        return components
    group_components = {}
    for c in components:
        group_components[c.group] = group_components.get(c.group, []) + [c]
    blessings = {}
    for group, components_from_group in group_components.items():
        algorithm = group_algorithms.get(group, default_algorithm)
        group_blessings = _calculate_group_blessings(
            components_from_group, algorithm)
        blessings.update(group_blessings)
    return [c._replace(blessing=blessings[(c.cid, c.mid)])
            for c in components]


def _calculate_group_blessings(components, algorithm):
    return {
        Algorithm.BLESS_ALL: _bless_all,
        Algorithm.BLESS_ONE: _bless_one}[algorithm](components)


def _bless_all(components):
    global _last_token_id
    ret = {}
    for c in components:
        if c.blessing is None:
            _last_token_id += 1
            blessing = _last_token_id
        else:
            blessing = c.blessing
        ret[(c.cid, c.mid)] = blessing
    return ret


def _bless_one(components):
    global _last_token_id
    min_rank = min(i.rank for i in components)
    min_rank_components = [i for i in components if i.rank == min_rank]
    highlander = util.first(min_rank_components,
                            lambda c: c.blessing is not None)
    if highlander:
        return {(i.cid, i.mid): highlander.blessing
                if i is highlander else None for i in components}
    if any(c.ready is not None for c in components):
        return {(i.cid, i.mid): None for i in components}
    highlander = min(min_rank_components, key=lambda i: i.mid)
    _last_token_id += 1
    return {(i.cid, i.mid): _last_token_id if i is highlander else None
            for i in components}
