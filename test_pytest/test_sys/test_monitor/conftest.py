import pytest
import time

import test_sys.test_monitor.common
import hat.monitor.common


@pytest.fixture
def sbs_repo():
    return hat.monitor.common.create_sbs_repo()


@pytest.fixture
def monitor_factory(tmp_path, unused_tcp_port_factory):
    processes = []

    def run_monitor(parent_infos=[], default_algorithm='BLESS_ALL',
                    group_algorithms={}, default_rank=1):
        monitor_port = unused_tcp_port_factory()
        master_port = unused_tcp_port_factory()
        ui_port = unused_tcp_port_factory()
        parents_ports = [info.master_port for info in parent_infos]

        process = test_sys.test_monitor.common.run_monitor_subprocess(
            conf=test_sys.test_monitor.common.create_monitor_conf(
                monitor_port=monitor_port,
                default_rank=default_rank,
                master_port=master_port,
                parents_ports=parents_ports,
                default_algorithm=default_algorithm,
                group_algorithms=group_algorithms,
                ui_port=ui_port),
            conf_folder_path=tmp_path)
        processes.append(process)
        while not test_sys.test_monitor.common.process_is_running(process):
            time.sleep(0.1)
        while not process.connections():
            time.sleep(0.1)

        return test_sys.test_monitor.common.ServerInfo(
            process=process,
            monitor_port=monitor_port,
            master_port=master_port,
            ui_port=ui_port,
            parents_ports=parents_ports,
            default_algorithm=default_algorithm,
            group_algorithms=group_algorithms,
            default_rank=default_rank)

    yield run_monitor

    for process in processes:
        test_sys.test_monitor.common.stop_process(process)


@pytest.fixture
def revived_monitor_factory(tmp_path):
    processes = []

    def rerun_monitor(server_info):
        process = test_sys.test_monitor.common.run_monitor_subprocess(
            conf=test_sys.test_monitor.common.create_monitor_conf(
                monitor_port=server_info.monitor_port,
                default_rank=server_info.default_rank,
                master_port=server_info.master_port,
                parents_ports=server_info.parents_ports,
                default_algorithm=server_info.default_algorithm,
                group_algorithms=server_info.group_algorithms,
                ui_port=server_info.ui_port),
            conf_folder_path=tmp_path)
        processes.append(process)
        while not test_sys.test_monitor.common.process_is_running(process):
            time.sleep(0.1)
        while not process.connections():
            time.sleep(0.1)

        return server_info._replace(process=process)

    yield rerun_monitor

    for process in processes:
        test_sys.test_monitor.common.stop_process(process)


@pytest.fixture
async def component_factory(sbs_repo):
    components = []

    async def create_component(name, group, server_info,
                               component_address=None):
        component = await test_sys.test_monitor.common.create_component_client(
            sbs_repo, name, group, server_info.monitor_port, component_address)

        components.append(component)
        return component

    yield create_component
    for component in components:
        await component.async_close()


@pytest.fixture
async def ui_client_factory():
    clients = []

    async def create_ui_client(server_info):
        address = f'ws://localhost:{server_info.ui_port}/ws'
        client = await test_sys.test_monitor.common.create_ui_client(address)
        clients.append(client)
        return client

    yield create_ui_client

    for client in clients:
        await client.async_close()


@pytest.fixture
def cluster_factory(monitor_factory, component_factory, ui_client_factory):
    async def create_cluster(group_conf,
                             parent_infos=[],
                             default_algorithm='BLESS_ALL',
                             default_rank=1):
        """
        group_conf is a dictionary with JSON data following this schema::

            type: object
            description: Keys are group names
            patternProperties:
                '(.+)':
                    type: object
                    required:
                        - components
                    properties:
                        components:
                            description: |
                                List of names of the components that belong in
                                the group
                            type: array
                            items:
                                type: string
                        algorithm:
                            description: |
                                Blessing algorithm of the group, BLESS_ALL if
                                not defined
                            enum:
                                - BLESS_ALL
                                - BLESS_ONE
        """
        group_algorithms = {
            group_name: group_settings['algorithm']
            for group_name, group_settings in group_conf.items()
            if 'algorithm' in group_settings}
        server_info = monitor_factory(parent_infos=parent_infos,
                                      default_algorithm=default_algorithm,
                                      group_algorithms=group_algorithms,
                                      default_rank=default_rank)
        components = {}
        for group in group_conf:
            components[group] = {}
            for component_name in group_conf[group]['components']:
                components[group][component_name] = await component_factory(
                    component_name,
                    group,
                    server_info)

        return test_sys.test_monitor.common.Cluster(
            server_info=server_info,
            components=components,
            ui_client=await ui_client_factory(server_info))

    return create_cluster
