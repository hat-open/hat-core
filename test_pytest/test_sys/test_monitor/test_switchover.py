import asyncio
import pytest
import time

from hat import util
import test_sys.test_monitor.common


@pytest.mark.timeout(10)
def test_switch_on_parent_kill(monitor_factory, revived_monitor_factory):
    parent1 = monitor_factory()
    parent2 = monitor_factory(parent_infos=[parent1])
    child = monitor_factory(parent_infos=[parent1, parent2])

    def find_connection_with_raddr(connections, ip, port):
        return util.first(connections,
                          lambda connection: (connection.raddr.port == port
                                              and connection.raddr.ip == ip
                                              if connection.raddr else False))

    assert find_connection_with_raddr(parent2.process.connections(),
                                      '127.0.0.1', parent1.master_port)
    assert find_connection_with_raddr(child.process.connections(),
                                      '127.0.0.1', parent1.master_port)
    assert not find_connection_with_raddr(child.process.connections(),
                                          '127.0.0.1', parent2.master_port)

    test_sys.test_monitor.common.stop_process(parent1.process)
    while not find_connection_with_raddr(child.process.connections(),
                                         '127.0.0.1', parent2.master_port):
        time.sleep(0.1)

    assert not find_connection_with_raddr(child.process.connections(),
                                          '127.0.0.1', parent1.master_port)
    parent1_lazarus = revived_monitor_factory(parent1)
    while not find_connection_with_raddr(child.process.connections(),
                                         '127.0.0.1',
                                         parent1_lazarus.master_port):
        time.sleep(0.1)


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_lose_blessing_when_lower_rank_connects(cluster_factory):
    group_name = 'group'
    cluster1 = await cluster_factory({
        group_name: {
            'algorithm': 'BLESS_ONE',
            'components': ['c1']}},
        default_rank=5)
    c1 = cluster1.components[group_name]['c1']

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()

    assert info1.blessing is not None
    assert info1.ready is None

    c1.client.set_ready(info1.blessing)

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()

    assert info1.blessing is not None
    assert info1.ready == info1.blessing

    cluster2 = await cluster_factory({
        group_name: {
            'components': ['c2']}},
        default_rank=1,
        parent_infos=[cluster1.server_info])
    c2 = cluster2.components[group_name]['c2']

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()
    info2, components2 = await c2.newest_state()

    assert info1.blessing is None
    assert info2.blessing is None

    c1.client.set_ready(info1.blessing)

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()
    info2, components2 = await c2.newest_state()

    assert info1.blessing is None
    assert info2.blessing is not None

    c2.client.set_ready(info2.blessing)

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()
    info2, components2 = await c2.newest_state()

    assert info1.blessing is None
    assert info2.blessing is not None
    assert info2.blessing == info2.ready


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_gain_blessing_when_blessed_disconnects(cluster_factory):
    group_name = 'group'
    cluster = await cluster_factory({
        group_name: {
            'algorithm': 'BLESS_ONE',
            'components': ['c1', 'c2']}},
        default_rank=5)
    c1 = cluster.components[group_name]['c1']
    c2 = cluster.components[group_name]['c2']

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()
    info2, components2 = await c2.newest_state()

    assert info1.blessing is not None
    assert info2.blessing is None

    c1.client.set_ready(info1.blessing)

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()
    info2, components2 = await c2.newest_state()

    assert info1.blessing
    assert info1.ready == info1.blessing
    assert info2.blessing is None

    await c1.client.async_close()

    await asyncio.sleep(0.1)
    info2, components2 = await c2.newest_state()

    assert info2.blessing is not None

    c2.client.set_ready(info2.blessing)

    await asyncio.sleep(0.1)
    info2, components2 = await c2.newest_state()

    assert info2.blessing is not None
    assert info2.blessing == info2.ready


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_rank_change_switchover(cluster_factory):
    group_name = 'group'
    cluster = await cluster_factory({
        group_name: {
            'algorithm': 'BLESS_ONE',
            'components': ['c1', 'c2']}},
        default_rank=5)
    c1 = cluster.components[group_name]['c1']
    c2 = cluster.components[group_name]['c2']
    ui_client = cluster.ui_client

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()
    info2, components2 = await c2.newest_state()

    assert info1.blessing is not None
    assert info2.blessing is None

    c1.client.set_ready(info1.blessing)

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()
    info2, components2 = await c2.newest_state()

    assert info1.blessing is not None
    assert info1.blessing == info1.ready
    assert info2.blessing is None

    await ui_client.set_rank(info2, 1)

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()
    info2, components2 = await c2.newest_state()

    assert info1.blessing is None
    assert info2.blessing is None

    c1.client.set_ready(None)

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()
    info2, components2 = await c2.newest_state()

    assert info1.blessing is None
    assert info1.ready is None
    assert info2.blessing is not None
    assert info2.ready is None

    c2.client.set_ready(info2.blessing)

    await asyncio.sleep(0.1)
    info1, components1 = await c1.newest_state()
    info2, components2 = await c2.newest_state()

    assert info1.blessing is None
    assert info1.ready is None
    assert info2.blessing is not None
    assert info2.ready == info2.blessing
