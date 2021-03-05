import pytest

from hat.monitor.common import ComponentInfo
from hat.monitor.server.blessing import (Algorithm,
                                         calculate)


generic_token = object()


def component_info(*, cid=0, mid=0, name='', group='', address=None, rank=1,
                   blessing=None, ready=None):
    return ComponentInfo(cid=cid,
                         mid=mid,
                         name=name,
                         group=group,
                         address=address,
                         rank=rank,
                         blessing=blessing,
                         ready=ready)


def group_component_infos(blessings, ranks, *, readies=None, starting_cid=0,
                          group=''):
    readies = readies or ([None] * len(blessings))
    temp_iter = enumerate(zip(blessings, ranks, readies))
    return [component_info(cid=starting_cid+i,
                           group=group,
                           rank=rank,
                           blessing=blessing,
                           ready=ready)
            for i, (blessing, rank, ready) in temp_iter]


@pytest.mark.parametrize("algorithm, components, result", [
    (Algorithm.BLESS_ALL, [], []),

    (Algorithm.BLESS_ONE, [], []),

    (Algorithm.BLESS_ALL,
     [component_info(cid=g_id * 10 + c_id, group=f'g{g_id}')
      for g_id in range(3)
      for c_id in range(5)],
     [component_info(cid=g_id * 10 + c_id, group=f'g{g_id}',
                     blessing=generic_token)
      for g_id in range(3)
      for c_id in range(5)]),

    (Algorithm.BLESS_ONE,
     group_component_infos(blessings=[None, None],
                           ranks=[1, 1]),
     group_component_infos(blessings=[generic_token, None],
                           ranks=[1, 1])),

    (Algorithm.BLESS_ONE,
     group_component_infos(blessings=[None, None],
                           ranks=[1, 2]),
     group_component_infos(blessings=[generic_token, None],
                           ranks=[1, 2])),

    (Algorithm.BLESS_ONE,
     group_component_infos(blessings=[None, None],
                           ranks=[2, 1]),
     group_component_infos(blessings=[None, generic_token],
                           ranks=[2, 1])),

    (Algorithm.BLESS_ONE,
     group_component_infos(blessings=[123, None],
                           ranks=[1, 1]),
     group_component_infos(blessings=[123, None],
                           ranks=[1, 1])),

    (Algorithm.BLESS_ONE,
     group_component_infos(blessings=[None, 123],
                           ranks=[1, 1]),
     group_component_infos(blessings=[None, 123],
                           ranks=[1, 1])),

    (Algorithm.BLESS_ONE,
     group_component_infos(blessings=[None, None],
                           ranks=[1, 1],
                           readies=[123, 456]),
     group_component_infos(blessings=[None, None],
                           ranks=[1, 1],
                           readies=[123, 456])),

    (Algorithm.BLESS_ONE,
     group_component_infos(blessings=[123, None],
                           ranks=[1, 1],
                           readies=[123, 456]),
     group_component_infos(blessings=[123, None],
                           ranks=[1, 1],
                           readies=[123, 456])),

    (Algorithm.BLESS_ONE,
     group_component_infos(blessings=[None, 456],
                           ranks=[1, 1],
                           readies=[123, 456]),
     group_component_infos(blessings=[None, 456],
                           ranks=[1, 1],
                           readies=[123, 456])),

    (Algorithm.BLESS_ONE,
     group_component_infos(blessings=[None, None],
                           ranks=[1, 2],
                           readies=[0, None]),
     group_component_infos(blessings=[None, generic_token],
                           ranks=[1, 2],
                           readies=[0, None])),

    (Algorithm.BLESS_ONE,
     group_component_infos(blessings=[None, None],
                           ranks=[1, 2],
                           readies=[0, 0]),
     group_component_infos(blessings=[None, None],
                           ranks=[1, 2],
                           readies=[0, 0])),
])
def test_calculate_blessing(algorithm, components, result):
    calculated_result = calculate(components, {}, algorithm)
    assert len(calculated_result) == len(result)
    for c1, c2 in zip(calculated_result, result):
        if c2.blessing is generic_token and c1.blessing is not None:
            c2 = c2._replace(blessing=c1.blessing)
        assert c1 == c2
