"""GUI server main"""

from pathlib import Path
import asyncio
import collections
import contextlib
import functools
import importlib
import itertools
import logging.config
import sys
import typing

import appdirs
import click

from hat import aio
from hat import json
import hat.event.client
import hat.event.common
import hat.gui.engine
import hat.gui.server
import hat.gui.view
import hat.monitor.client


package_path: Path = Path(__file__).parent
"""Python package path"""

user_conf_dir: Path = Path(appdirs.user_config_dir('hat'))
"""User configuration directory path"""

default_ui_path: Path = package_path / 'ui'
"""Default web ui directory path"""


@click.command()
@click.option('--conf', default=None, metavar='PATH', type=Path,
              help="configuration defined by hat://gui/main.yaml# "
                   "(default $XDG_CONFIG_HOME/hat/gui.{yaml|yml|json})")
@click.option('--ui-path', default=default_ui_path, metavar='PATH', type=Path,
              help="Override web ui directory path (development argument)")
def main(conf: typing.Optional[Path],
         ui_path: Path):
    """GUI Server"""
    aio.init_asyncio()

    if not conf:
        for suffix in ('.yaml', '.yml', '.json'):
            conf = (user_conf_dir / 'gui').with_suffix(suffix)
            if conf.exists():
                break
    conf = json.decode_file(conf)
    hat.gui.common.json_schema_repo.validate('hat://gui/main.yaml#', conf)

    for adapter_conf in conf['adapters']:
        module = importlib.import_module(adapter_conf['module'])
        if module.json_schema_repo and module.json_schema_id:
            module.json_schema_repo.validate(module.json_schema_id,
                                             adapter_conf)

    logging.config.dictConfig(conf['log'])

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf, ui_path))


async def async_main(conf: json.Data,
                     ui_path: Path):
    """Async main entry point"""
    async_group = aio.Group()

    try:
        monitor = await hat.monitor.client.connect(conf['monitor'])
        _bind_resource(async_group, monitor)

        component = hat.monitor.client.Component(monitor, run_with_monitor,
                                                 conf, ui_path, monitor)
        component.set_enabled(True)
        _bind_resource(async_group, component)

        await async_group.wait_closing()

    finally:
        await aio.uncancellable(monitor.async_close())


async def run_with_monitor(component: hat.monitor.client.Component,
                           conf: json.Data,
                           ui_path: Path,
                           monitor: hat.monitor.client.Client):
    """Run monitor component"""
    subscription = await _create_subscription(conf)
    subscriptions = list(subscription.get_query_types())

    run_cb = functools.partial(run_with_event, conf, ui_path)

    await hat.event.client.run_client(monitor, conf['event_server_group'],
                                      run_cb, subscriptions)


async def run_with_event(conf: json.Data,
                         ui_path: Path,
                         client: hat.event.client.Client):
    """Run event client"""
    async_group = aio.Group()

    try:
        engine = await hat.gui.engine.create_engine(conf, client)
        _bind_resource(async_group, engine)

        views = await hat.gui.view.create_view_manager(conf)
        _bind_resource(async_group, views)

        server = await hat.gui.server.create_server(conf, ui_path,
                                                    engine.adapters, views)
        _bind_resource(async_group, server)

        await async_group.wait_closing()

    finally:
        await aio.uncancellable(async_group.async_close())


def _bind_resource(async_group, resource):
    async_group.spawn(aio.call_on_cancel, resource.async_close)
    async_group.spawn(aio.call_on_done, resource.wait_closing(),
                      async_group.close)


async def _create_subscription(conf):
    subscriptions = collections.deque()
    for adapter_conf in conf['adapters']:
        module = importlib.import_module(adapter_conf['module'])
        subscription = await aio.call(module.create_subscription, adapter_conf)
        subscriptions.append(subscription)

    query_types = itertools.chain.from_iterable(i.get_query_types()
                                                for i in subscriptions)
    return hat.event.common.Subscription(query_types)


if __name__ == '__main__':
    sys.argv[0] = 'hat-gui'
    sys.exit(main())
