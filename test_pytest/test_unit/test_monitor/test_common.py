import pytest

from hat.monitor.server import common


infos = [common.ComponentInfo(cid=1,
                              mid=2,
                              name='name',
                              group='group',
                              address='address',
                              rank=3,
                              blessing=4,
                              ready=5),
         common.ComponentInfo(cid=1,
                              mid=2,
                              name='name',
                              group='group',
                              address=None,
                              rank=3,
                              blessing=None,
                              ready=None)]

msg_clients = [common.MsgClient(name='name',
                                group='group',
                                address='address',
                                ready=1),
               common.MsgClient(name='name',
                                group='group',
                                address=None,
                                ready=None)]

msg_servers = [common.MsgServer(cid=1,
                                mid=2,
                                components=infos),
               common.MsgServer(cid=1,
                                mid=2,
                                components=[])]

msg_slaves = [common.MsgSlave(components=infos),
              common.MsgSlave(components=[])]

msg_masters = [common.MsgMaster(mid=1,
                                components=infos),
               common.MsgMaster(mid=1,
                                components=[])]


@pytest.mark.parametrize("info", infos)
def test_component_info(info):
    data = common.sbs_repo.encode(
        'HatMonitor', 'ComponentInfo', common.component_info_to_sbs(info))
    result = common.component_info_from_sbs(
        common.sbs_repo.decode('HatMonitor', 'ComponentInfo', data))
    assert result == info


@pytest.mark.parametrize("msg_client", msg_clients)
def test_msg_client(msg_client):
    data = common.sbs_repo.encode(
        'HatMonitor', 'MsgClient', common.msg_client_to_sbs(msg_client))
    result = common.msg_client_from_sbs(
        common.sbs_repo.decode('HatMonitor', 'MsgClient', data))
    assert result == msg_client


@pytest.mark.parametrize("msg_server", msg_servers)
def test_msg_server(msg_server):
    data = common.sbs_repo.encode(
        'HatMonitor', 'MsgServer', common.msg_server_to_sbs(msg_server))
    result = common.msg_server_from_sbs(
        common.sbs_repo.decode('HatMonitor', 'MsgServer', data))
    assert result == msg_server


@pytest.mark.parametrize("msg_slave", msg_slaves)
def test_msg_slave(msg_slave):
    data = common.sbs_repo.encode(
        'HatMonitor', 'MsgSlave', common.msg_slave_to_sbs(msg_slave))
    result = common.msg_slave_from_sbs(
        common.sbs_repo.decode('HatMonitor', 'MsgSlave', data))
    assert result == msg_slave


@pytest.mark.parametrize("msg_master", msg_masters)
def test_msg_master(msg_master):
    data = common.sbs_repo.encode(
        'HatMonitor', 'MsgMaster', common.msg_master_to_sbs(msg_master))
    result = common.msg_master_from_sbs(
        common.sbs_repo.decode('HatMonitor', 'MsgMaster', data))
    assert result == msg_master
