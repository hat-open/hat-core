from pathlib import Path
import argparse
import asyncio
import contextlib
import functools
import importlib
import logging.config
import sys

import appdirs

from hat import aio
from hat import json
from hat.gui import common
import hat.event.client
import hat.event.common
import hat.gui.common
import hat.gui.server
import hat.gui.view
import hat.monitor.client
import hat.monitor.common


package_path = Path(__file__).parent
user_conf_dir = Path(appdirs.user_config_dir('hat'))

default_ui_path = package_path / 'ui'
default_conf_path = user_conf_dir / 'gui.yaml'


def main():
    """Main"""
    aio.init_asyncio()

    args = create_parser().parse_args()
    conf = json.decode_file(args.conf)
    hat.gui.common.json_schema_repo.validate('hat://gui/main.yaml#', conf)

    for adapter_conf in conf['adapters']:
        module = importlib.import_module(adapter_conf['module'])
        if module.json_schema_repo and module.json_schema_id:
            module.json_schema_repo.validate(module.json_schema_id,
                                             adapter_conf)

    logging.config.dictConfig(conf['log'])

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf, args.ui_path))


async def async_main(conf, ui_path):
    """Async main

    Args:
        conf (json.Data): configuration defined by ``hat://gui/main.yaml#``
        ui_path (pathlib.Path): web ui directory path

    """
    monitor = await hat.monitor.client.connect(conf['monitor'])
    try:
        await hat.monitor.client.run_component(
            monitor, run_with_monitor, conf, ui_path, monitor)
    finally:
        await aio.uncancellable(monitor.async_close())


async def run_with_monitor(conf, ui_path, monitor):
    """Run with monitor client

    Args:
        conf (json.Data): configuration defined by ``hat://gui/main.yaml#``
        ui_path (pathlib.Path): web ui directory path
        monitor (hat.monitor.client.Client): monitor client

    """
    subscriptions = set()
    for adapter_conf in conf['adapters']:
        module = importlib.import_module(adapter_conf['module'])
        if module.event_type_prefix is not None:
            subscriptions.add(tuple(module.event_type_prefix + ['*']))
    subscriptions = [list(i) for i in subscriptions]

    run_cb = functools.partial(run_with_event, conf, ui_path)
    await hat.event.client.run_client(
        monitor, conf['event_server_group'], run_cb, subscriptions)


async def run_with_event(conf, ui_path, client):
    """Run with event client

    Args:
        conf (json.Data): configuration defined by ``hat://gui/main.yaml#``
        ui_path (pathlib.Path): web ui directory path
        client (hat.event.client.Client): event client

    """
    async_group = aio.Group()

    try:
        factory = AdapterEventClientFactory(client)
        async_group.spawn(aio.call_on_cancel, factory.async_close)

        adapters = {}
        for adapter_conf in conf['adapters']:
            name = adapter_conf['name']
            if name in adapters:
                raise Exception(f'adapter name {name} not unique')
            module = importlib.import_module(adapter_conf['module'])
            adapter_event_client = factory.create(module.event_type_prefix)
            adapter = await module.create(adapter_conf, adapter_event_client)
            async_group.spawn(aio.call_on_cancel, adapter.async_close)
            adapters[name] = adapter

        views = await hat.gui.view.create_view_manager(conf['views'])
        async_group.spawn(aio.call_on_cancel, views.async_close)

        server = await hat.gui.server.create(conf['server'], ui_path,
                                             adapters, views)
        async_group.spawn(aio.call_on_cancel, server.async_close)

        await asyncio.wait([*(async_group.spawn(adapter.wait_closed)
                              for adapter in adapters.values()),
                            async_group.spawn(views.wait_closed),
                            async_group.spawn(server.wait_closed)],
                           return_when=asyncio.FIRST_COMPLETED)
    finally:
        await aio.uncancellable(async_group.async_close())


class AdapterEventClientFactory(aio.Resource):
    """Adapter event client factory

    Args:
        client (hat.event.client.Client): event client

    """

    def __init__(self, client):
        self._client = client
        self._queues = []
        self._async_group = aio.Group()
        self._async_group.spawn(self._receive_loop)

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    def create(self, event_type_prefix):
        """Create adapter event client

        Args:
            event_type_prefix (hat.event.common.EventType): event_type_prefix

        Returns:
            common.AdapterEventClient

        """
        queue = aio.Queue()
        self._async_group.spawn(aio.call_on_cancel, queue.close)
        if event_type_prefix is not None:
            self._queues.append((event_type_prefix, queue))
        return _AdapterEventClientImpl(self._client, queue)

    async def _receive_loop(self):
        try:
            while True:
                events = await self._client.receive()
                for prefix, queue in self._queues:
                    filtered_events = [
                        event for event in events
                        if event.event_type[:len(prefix)] == prefix]
                    if filtered_events:
                        queue.put_nowait(filtered_events)
        finally:
            self._async_group.close()


class _AdapterEventClientImpl(common.AdapterEventClient):

    def __init__(self, client, queue):
        self._queue = queue
        self._client = client

    async def receive(self):
        return await self._queue.get()

    def register(self, events):
        self._client.register(events)

    async def register_with_response(self, events):
        return await self._client.register_with_response(events)

    async def query(self, data):
        return await self._client.query(data)


def create_parser():
    """Create command line arguments parser

    Returns:
        argparse.ArgumentParser

    """
    parser = argparse.ArgumentParser(prog='hat-gui')
    parser.add_argument(
        '--conf', metavar='path', dest='conf',
        default=default_conf_path, type=Path,
        help="configuration defined by hat://gui/main.yaml# "
             "(default $XDG_CONFIG_HOME/hat/gui.yaml)")

    dev_args = parser.add_argument_group('development arguments')
    dev_args.add_argument(
        '--ui-path', metavar='path', dest='ui_path',
        default=default_ui_path, type=Path,
        help="override web ui directory path")
    return parser


if __name__ == '__main__':
    sys.exit(main())
