import asyncio
import pytest

from hat import util

from test_sys.test_monitor import common


@pytest.mark.timeout(10)
def test_server_listens(monitor_factory):
    server_info = monitor_factory()

    connections = server_info.process.connections()
    for port in {server_info.ui_port, server_info.monitor_port,
                 server_info.master_port}:
        assert util.first(connections, lambda c: (c.laddr.ip == '0.0.0.0'
                                                  and c.laddr.port == port))


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_single_component(monitor_factory, component_factory,
                                ui_client_factory):
    server_info = monitor_factory()

    component_name = 'name'
    component_group = 'group'
    component = await component_factory(component_name, component_group,
                                        server_info)
    ui_client = await ui_client_factory(server_info)

    info, components = await component.next_state()
    assert info is None
    assert components == []

    info, components = await component.next_state()
    assert info.name == component_name
    assert info.group == component_group
    assert info.rank == 1
    assert info.blessing is not None
    assert info.ready is None
    assert components == [info]

    ui_state = await ui_client.get_state()
    ui_info = common.find_ui_info(ui_state, info)
    assert ui_info
    assert ui_info['name'] == info.name
    assert ui_info['group'] == info.group

    component.client.set_ready(info.blessing)
    info, components = await component.next_state()
    assert info.blessing is not None
    assert info.ready is not None
    assert info.ready == info.blessing
    assert components == [info]

    ui_state = await ui_client.get_state()
    ui_info = common.find_ui_info(ui_state, info)
    assert ui_info
    assert ui_info['blessing'] == info.blessing
    assert ui_info['ready'] == ui_info['blessing']

    component.client.set_ready(None)
    info, components = await component.next_state()
    assert info.ready is None
    assert info.blessing != info.ready
    assert components == [info]

    ui_state = await ui_client.get_state()
    ui_info = common.find_ui_info(ui_state, info)
    assert ui_info
    assert ui_info['blessing'] == info.blessing
    assert ui_info['ready'] is None

    await ui_client.set_rank(info, 5)
    info, components = await component.next_state()
    assert info.rank == 5

    ui_state = await ui_client.get_state()
    ui_info = common.find_ui_info(ui_state, info)
    assert ui_info['rank'] == 5


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_bless_all(cluster_factory):
    cluster = await cluster_factory({
        'g1': {'components': ['c1', 'c2']},
        'g2': {'components': ['c3']}})

    component1 = cluster.components['g1']['c1']
    component2 = cluster.components['g1']['c2']
    component3 = cluster.components['g2']['c3']
    ui_client = cluster.ui_client

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    info3, components3 = await component3.newest_state()
    ui_state = await ui_client.get_state()

    assert components1 == components2 and components2 == components3
    assert info1.blessing is not None
    assert info2.blessing is not None
    assert info3.blessing is not None
    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)
    ui_info3 = common.find_ui_info(ui_state, info3)
    assert ui_info1 and ui_info2 and ui_info3
    assert ui_info1['blessing'] is not None
    assert ui_info2['blessing'] is not None
    assert ui_info3['blessing'] is not None

    component1.client.set_ready(info1.blessing)
    component2.client.set_ready(info2.blessing)
    component3.client.set_ready(info3.blessing)

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    info3, components3 = await component3.newest_state()
    ui_state = await ui_client.get_state()

    assert info1.blessing is not None
    assert info2.blessing is not None
    assert info3.blessing is not None
    assert info1.ready == info1.blessing
    assert info2.ready == info2.blessing
    assert info3.ready == info3.blessing

    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)
    ui_info3 = common.find_ui_info(ui_state, info3)
    assert ui_info1 and ui_info2 and ui_info3
    assert ui_info1['ready'] == ui_info1['blessing']
    assert ui_info2['ready'] == ui_info2['blessing']
    assert ui_info3['ready'] == ui_info3['blessing']

    await ui_client.set_rank(info1, 6)
    await ui_client.set_rank(info2, 2)
    await ui_client.set_rank(info3, 4)

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    info3, components3 = await component3.newest_state()
    ui_state = await ui_client.get_state()
    assert info1.blessing is not None
    assert info2.blessing is not None
    assert info3.blessing is not None
    assert info1.rank == 6
    assert info2.rank == 2
    assert info3.rank == 4


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_bless_one(cluster_factory):
    cluster = await cluster_factory({
        'group': {
            'components': ['c1', 'c2']}
        }, default_algorithm='BLESS_ONE')

    component1 = cluster.components['group']['c1']
    component2 = cluster.components['group']['c2']
    ui_client = cluster.ui_client

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state = await ui_client.get_state()
    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)

    assert info1.blessing is not None
    assert info2.blessing is None
    assert ui_info1['blessing'] == info1.blessing
    assert ui_info2['blessing'] is None

    component1.client.set_ready(info1.blessing)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state = await ui_client.get_state()
    ui_info1 = common.find_ui_info(ui_state, info1)

    assert info1.ready == info1.blessing
    assert ui_info1['ready'] == info1.ready
    assert ui_info1['blessing'] == ui_info1['ready']

    await ui_client.set_rank(info1, 10)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state = await ui_client.get_state()
    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is None
    assert ui_info1['blessing'] is None
    assert ui_info2['blessing'] is None

    component1.client.set_ready(None)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state = await ui_client.get_state()
    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is not None
    assert ui_info1['blessing'] is None
    assert ui_info2['blessing'] == info2.blessing

    component2.client.set_ready(info2.blessing)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state = await ui_client.get_state()
    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is not None and info2.blessing == info2.ready
    assert ui_info1['blessing'] is None
    assert ui_info2['ready'] == info2.ready


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_bless_all_group_setting(cluster_factory):
    cluster = await cluster_factory({
        'group': {
            'algorithm': 'BLESS_ALL',
            'components': ['c1', 'c2']}
        }, default_algorithm='BLESS_ONE')

    component1 = cluster.components['group']['c1']
    component2 = cluster.components['group']['c2']
    ui_client = cluster.ui_client

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state = await ui_client.get_state()

    assert components1 == components2
    assert info1.blessing is not None
    assert info2.blessing is not None
    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)
    assert ui_info1 and ui_info2
    assert ui_info1['blessing']
    assert ui_info2['blessing']

    component1.client.set_ready(info1.blessing)
    component2.client.set_ready(info2.blessing)

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state = await ui_client.get_state()

    assert info1.ready == info1.blessing
    assert info2.ready == info2.blessing

    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)
    assert ui_info1 and ui_info2
    assert ui_info1['ready'] == ui_info1['blessing']
    assert ui_info2['ready'] == ui_info2['blessing']

    await ui_client.set_rank(info1, 6)
    await ui_client.set_rank(info2, 2)

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state = await ui_client.get_state()
    assert info1.blessing is not None and info2.blessing is not None
    assert info1.rank == 6
    assert info2.rank == 2


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_bless_one_group_setting(cluster_factory):
    cluster = await cluster_factory(group_conf={
        'redundant': {
            'algorithm': 'BLESS_ONE',
            'components': ['primary', 'secondary']}})
    primary = cluster.components['redundant']['primary']
    secondary = cluster.components['redundant']['secondary']
    ui_client = cluster.ui_client

    await asyncio.sleep(0.5)

    info1, components1 = await primary.newest_state()
    info2, components2 = await secondary.newest_state()
    ui_state = await ui_client.get_state()
    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)

    assert info1.blessing is not None
    assert info2.blessing is None
    assert ui_info1['blessing'] == info1.blessing
    assert ui_info2['blessing'] is None

    primary.client.set_ready(info1.blessing)
    await asyncio.sleep(0.5)

    info1, components1 = await primary.newest_state()
    info2, components2 = await secondary.newest_state()
    ui_state = await ui_client.get_state()
    ui_info1 = common.find_ui_info(ui_state, info1)

    assert info1.ready == info1.blessing
    assert ui_info1['ready'] == info1.ready
    assert ui_info1['blessing'] == ui_info1['ready']

    await ui_client.set_rank(info1, 10)
    await asyncio.sleep(0.5)

    info1, components1 = await primary.newest_state()
    info2, components2 = await secondary.newest_state()
    ui_state = await ui_client.get_state()
    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is None
    assert ui_info1['blessing'] is None
    assert ui_info2['blessing'] is None

    primary.client.set_ready(None)
    await asyncio.sleep(0.5)

    info1, components1 = await primary.newest_state()
    info2, components2 = await secondary.newest_state()
    ui_state = await ui_client.get_state()
    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is not None
    assert ui_info1['blessing'] is None
    assert ui_info2['blessing'] == info2.blessing

    secondary.client.set_ready(info2.blessing)
    await asyncio.sleep(0.5)

    info1, components1 = await primary.newest_state()
    info2, components2 = await secondary.newest_state()
    ui_state = await ui_client.get_state()
    ui_info1 = common.find_ui_info(ui_state, info1)
    ui_info2 = common.find_ui_info(ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is not None and info2.blessing == info2.ready
    assert ui_info1['blessing'] is None
    assert ui_info2['ready'] == info2.ready


@pytest.mark.timeout(10)
def test_master_slave(monitor_factory):
    slave = monitor_factory()
    master = monitor_factory(parent_infos=[slave])
    assert util.first(master.process.connections(),
                      lambda conn: (conn.raddr.port == slave.master_port
                                    and conn.raddr.ip == '127.0.0.1'
                                    if conn.raddr else False))


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_peers_bless_all(cluster_factory):
    group_name = 'group'
    c1_name = 'c1'
    c2_name = 'c2'
    master_cluster = await cluster_factory({
        group_name: {'components': [c1_name]}})
    slave_cluster = await cluster_factory({
        group_name: {'components': [c2_name]}},
        parent_infos=[master_cluster.server_info])
    component1 = master_cluster.components[group_name][c1_name]
    component2 = slave_cluster.components[group_name][c2_name]
    master_ui_client = master_cluster.ui_client
    slave_ui_client = slave_cluster.ui_client

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state_master = await master_ui_client.get_state()
    ui_state_slave = await slave_ui_client.get_state()

    assert components1 == components2
    assert info1.blessing is not None
    assert info2.blessing is not None

    assert ui_state_master['components'] == ui_state_slave['components']
    ui_info1 = common.find_ui_info(ui_state_master, info1)
    ui_info2 = common.find_ui_info(ui_state_master, info2)

    assert ui_info1 and ui_info2
    assert ui_info1['blessing'] is not None
    assert ui_info2['blessing'] is not None

    component1.client.set_ready(info1.blessing)
    component2.client.set_ready(info2.blessing)

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state_master = await master_ui_client.get_state()

    assert info1.ready == info1.blessing
    assert info2.ready == info2.blessing

    ui_info1 = common.find_ui_info(ui_state_master, info1)
    ui_info2 = common.find_ui_info(ui_state_master, info2)
    assert ui_info1 and ui_info2
    assert ui_info1['ready'] == ui_info1['blessing']
    assert ui_info2['ready'] == ui_info2['blessing']

    await master_ui_client.set_rank(info1, 6)
    await master_ui_client.set_rank(info2, 2)

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    ui_state_master = await master_ui_client.get_state()
    assert info1.blessing is not None and info2.blessing is not None
    assert info1.rank == 6
    assert info2.rank == 2


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_peers_bless_one(cluster_factory):
    group_name = 'group'
    c1_name = 'c1'
    c2_name = 'c2'
    master_cluster = await cluster_factory({
        group_name: {'components': [c1_name]}},
        default_algorithm='BLESS_ONE')
    slave_cluster = await cluster_factory({
        group_name: {'components': [c2_name]}},
        parent_infos=[master_cluster.server_info])
    component1 = master_cluster.components[group_name][c1_name]
    component2 = slave_cluster.components[group_name][c2_name]
    master_ui_client = master_cluster.ui_client
    slave_ui_client = slave_cluster.ui_client

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)
    ui_info2 = common.find_ui_info(master_ui_state, info2)

    assert info1.blessing is not None
    assert info2.blessing is None
    assert ui_info1['blessing'] == info1.blessing
    assert ui_info2['blessing'] is None

    component1.client.set_ready(info1.blessing)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)

    assert info1.ready == info1.blessing
    assert ui_info1['ready'] == info1.ready
    assert ui_info1['blessing'] == ui_info1['ready']

    await master_ui_client.set_rank(info1, 10)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)
    ui_info2 = common.find_ui_info(master_ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is None
    assert ui_info1['blessing'] is None
    assert ui_info2['blessing'] is None

    component1.client.set_ready(None)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)
    ui_info2 = common.find_ui_info(master_ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is not None
    assert ui_info1['blessing'] is None
    assert ui_info2['blessing'] == info2.blessing

    component2.client.set_ready(info2.blessing)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)
    ui_info2 = common.find_ui_info(master_ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is not None and info2.blessing == info2.ready
    assert ui_info1['blessing'] is None
    assert ui_info2['ready'] == info2.ready


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_peers_bless_all_group(cluster_factory):
    group_name = 'group'
    c1_name = 'c1'
    c2_name = 'c2'
    master_cluster = await cluster_factory({
        group_name: {
            'components': [c1_name],
            'algorithm': 'BLESS_ALL'}},
        default_algorithm='BLESS_ONE')
    slave_cluster = await cluster_factory({
        group_name: {'components': [c2_name]}},
        parent_infos=[master_cluster.server_info])
    component1 = master_cluster.components[group_name][c1_name]
    component2 = slave_cluster.components[group_name][c2_name]
    master_ui_client = master_cluster.ui_client
    slave_ui_client = slave_cluster.ui_client

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert components1 == components2
    assert info1.blessing is not None
    assert info2.blessing is not None

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)
    ui_info2 = common.find_ui_info(master_ui_state, info2)
    assert ui_info1 and ui_info2
    assert ui_info1['blessing']
    assert ui_info2['blessing']

    component1.client.set_ready(info1.blessing)
    component2.client.set_ready(info2.blessing)

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert info1.ready == info1.blessing
    assert info2.ready == info2.blessing

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)
    ui_info2 = common.find_ui_info(master_ui_state, info2)
    assert ui_info1 and ui_info2
    assert ui_info1['ready'] == ui_info1['blessing']
    assert ui_info2['ready'] == ui_info2['blessing']

    await master_ui_client.set_rank(info1, 6)
    await master_ui_client.set_rank(info2, 2)

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    assert info1.blessing is not None and info2.blessing is not None
    assert info1.rank == 6
    assert info2.rank == 2


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_peers_bless_one_group(cluster_factory):
    group_name = 'group'
    c1_name = 'c1'
    c2_name = 'c2'
    master_cluster = await cluster_factory({
        group_name: {
            'components': [c1_name],
            'algorithm': 'BLESS_ONE'}})
    slave_cluster = await cluster_factory({
        group_name: {'components': [c2_name]}},
        parent_infos=[master_cluster.server_info])
    component1 = master_cluster.components[group_name][c1_name]
    component2 = slave_cluster.components[group_name][c2_name]
    master_ui_client = master_cluster.ui_client
    slave_ui_client = slave_cluster.ui_client

    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)
    ui_info2 = common.find_ui_info(master_ui_state, info2)

    assert info1.blessing is not None
    assert info2.blessing is None
    assert ui_info1['blessing'] == info1.blessing
    assert ui_info2['blessing'] is None

    component1.client.set_ready(info1.blessing)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)

    assert info1.ready == info1.blessing
    assert ui_info1['ready'] == info1.ready
    assert ui_info1['blessing'] == ui_info1['ready']

    await master_ui_client.set_rank(info1, 10)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)
    ui_info2 = common.find_ui_info(master_ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is None
    assert ui_info1['blessing'] is None
    assert ui_info2['blessing'] is None

    component1.client.set_ready(None)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)
    ui_info2 = common.find_ui_info(master_ui_state, info2)

    assert info1.blessing is None
    assert info2.blessing is not None
    assert ui_info1['blessing'] is None
    assert ui_info2['blessing'] == info2.blessing

    component2.client.set_ready(info2.blessing)
    await asyncio.sleep(0.5)

    info1, components1 = await component1.newest_state()
    info2, components2 = await component2.newest_state()
    master_ui_state = await master_ui_client.get_state()
    slave_ui_state = await slave_ui_client.get_state()

    assert master_ui_state['components'] == slave_ui_state['components']
    ui_info1 = common.find_ui_info(master_ui_state, info1)
    ui_info2 = common.find_ui_info(master_ui_state, info2)

    assert info1.blessing is None
    assert ui_info2['ready'] == info2.ready


@pytest.mark.timeout(10)
@pytest.mark.asyncio
@pytest.mark.parametrize('cluster_confs', [
    [{
        'groups': {
            'target_group': {
                'components': ['c1', 'c2', 'c3']}},
            'default_algorithm': 'BLESS_ALL'}],
    [{
        'groups': {
            'target_group': {
                'components': ['c1', 'c2', 'c3'],
                'algorithm': 'BLESS_ALL'}},
            'default_algorithm': 'BLESS_ONE'}],
    [{
        'groups': {
            'target_group': {
                'components': ['c1', 'c2']}},
            'default_algorithm': 'BLESS_ALL'},
     {
        'groups': {
            'target_group': {
                'components': ['c3', 'c4']}},
            'default_algorithm': 'BLESS_ALL'}],
    [{
        'groups': {
            'target_group': {
                'components': ['c1', 'c2'],
                'algorithm': 'BLESS_ALL'}},
            'default_algorithm': 'BLESS_ONE'},
     {
        'groups': {
            'target_group': {
                'components': ['c3', 'c4']}},
            'default_algorithm': 'BLESS_ALL'}],
    [{
        'groups': {
            'target_group': {
                'components': ['c1', 'c2'],
                'algorithm': 'BLESS_ALL'}},
            'default_algorithm': 'BLESS_ONE'},
     {
        'groups': {
            'target_group': {
                'components': ['c3', 'c4'],
                'algorithm': 'BLESS_ONE'}},
            'default_algorithm': 'BLESS_ONE'}],
])
async def test_bless_all_behavior(cluster_factory, cluster_confs):
    clusters = []
    target_components = []
    ui_clients = []
    for conf in cluster_confs:
        cluster = await cluster_factory(
            group_conf=conf['groups'],
            default_algorithm=conf['default_algorithm'],
            parent_infos=[cluster.server_info for cluster in clusters],
            default_rank=1)
        target_components.extend(
            cluster.components['target_group'].values())
        clusters.append(cluster)
        ui_clients.append(cluster.ui_client)

    await asyncio.sleep(0.5)
    ui_states = [await ui_client.get_state() for ui_client in ui_clients]
    assert all([state['components'] == ui_states[0]['components']
                for state in ui_states])

    master_ui_state = ui_states[0]
    for component in target_components:
        info, components = await component.newest_state()
        ui_info = common.find_ui_info(master_ui_state, info)
        assert info.blessing is not None
        assert ui_info['blessing'] is not None
        assert info.blessing == ui_info['blessing']
        component.client.set_ready(info.blessing)

    await asyncio.sleep(0.5)
    ui_states = [await ui_client.get_state() for ui_client in ui_clients]
    assert all([state['components'] == ui_states[0]['components']
                for state in ui_states])

    master_ui_state = ui_states[0]
    for component in target_components:
        info, components = await component.newest_state()
        ui_info = common.find_ui_info(master_ui_state, info)
        assert info.blessing is not None
        assert info.ready is not None
        assert info.blessing == info.ready
        assert ui_info['blessing'] is not None
        assert ui_info['ready'] is not None
        assert ui_info['blessing'] == ui_info['ready']
        assert ui_info['blessing'] == info.ready


@pytest.mark.timeout(10)
@pytest.mark.asyncio
@pytest.mark.parametrize('cluster_confs', [
    [{
        'groups': {
            'target_group': {
                'components': ['c1', 'c2', 'c3']}},
            'default_algorithm': 'BLESS_ONE'}],
    [{
        'groups': {
            'target_group': {
                'components': ['c1', 'c2', 'c3'],
                'algorithm': 'BLESS_ONE'}},
            'default_algorithm': 'BLESS_ALL'}],
    [{
        'groups': {
            'target_group': {
                'components': ['c1', 'c2']}},
            'default_algorithm': 'BLESS_ONE'},
     {
        'groups': {
            'target_group': {
                'components': ['c3', 'c4']}},
            'default_algorithm': 'BLESS_ONE'}],
    [{
        'groups': {
            'target_group': {
                'components': ['c1', 'c2'],
                'algorithm': 'BLESS_ONE'}},
            'default_algorithm': 'BLESS_ONE'},
     {
        'groups': {
            'target_group': {
                'components': ['c3', 'c4']}},
            'default_algorithm': 'BLESS_ONE'}],
    [{
        'groups': {
            'target_group': {
                'components': ['c1', 'c2'],
                'algorithm': 'BLESS_ONE'}},
            'default_algorithm': 'BLESS_ALL'},
     {
        'groups': {
            'target_group': {
                'components': ['c3', 'c4'],
                'algorithm': 'BLESS_ALL'}},
            'default_algorithm': 'BLESS_ALL'}],
])
async def test_bless_one_behavior(cluster_factory, cluster_confs):
    clusters = []
    target_components = []
    ui_clients = []
    for conf in cluster_confs:
        cluster = await cluster_factory(
            group_conf=conf['groups'],
            default_algorithm=conf['default_algorithm'],
            parent_infos=[cluster.server_info for cluster in clusters],
            default_rank=1)
        target_components.extend(
            cluster.components['target_group'].values())
        clusters.append(cluster)
        ui_clients.append(cluster.ui_client)

    await asyncio.sleep(0.5)
    ui_states = [await ui_client.get_state() for ui_client in ui_clients]
    assert all([state['components'] == ui_states[0]['components']
                for state in ui_states])

    ui_state = ui_states[0]
    blessings_count = 0
    for component in target_components:
        info, components = await component.newest_state()
        ui_info = common.find_ui_info(ui_state, info)
        if info.blessing is not None:
            assert ui_info['blessing'] == info.blessing
            blessings_count += 1
        else:
            assert ui_info['blessing'] is None
        component.client.set_ready(info.blessing)

    assert blessings_count == 1

    await asyncio.sleep(0.5)
    ui_states = [await ui_client.get_state() for ui_client in ui_clients]
    assert all([state['components'] == ui_states[0]['components']
                for state in ui_states])

    ui_state = ui_states[0]
    blessed_index = None
    for (i, component) in enumerate(target_components):
        info, components = await component.newest_state()
        ui_info = common.find_ui_info(ui_state, info)
        if info.blessing is not None:
            assert info.blessing == info.ready
            assert ui_info['ready'] == info.ready
            assert ui_info['blessing'] == ui_info['ready']

            await ui_clients[0].set_rank(info, 5)
            blessed_index = i
        else:
            assert info.ready is None
            assert ui_info['ready'] is None
            assert ui_info['blessing'] is None

    await asyncio.sleep(0.5)
    ui_states = [await ui_client.get_state() for ui_client in ui_clients]
    assert all([state['components'] == ui_states[0]['components']
                for state in ui_states])

    ui_state = ui_states[0]
    for (i, component) in enumerate(target_components):
        info, components = await component.newest_state()
        ui_info = common.find_ui_info(ui_state, info)
        assert info.blessing is None
        assert ui_info['blessing'] is None
        component.client.set_ready(info.blessing)

    await asyncio.sleep(0.5)
    ui_states = [await ui_client.get_state() for ui_client in ui_clients]
    assert all([state['components'] == ui_states[0]['components']
                for state in ui_states])

    ui_state = ui_states[0]
    blessings_count = 0
    for (i, component) in enumerate(target_components):
        info, components = await component.newest_state()
        ui_info = common.find_ui_info(ui_state, info)
        if info.blessing is not None:
            assert i != blessed_index
            assert ui_info['blessing'] == info.blessing
            blessings_count += 1
        component.client.set_ready(info.blessing)

    assert blessings_count == 1
