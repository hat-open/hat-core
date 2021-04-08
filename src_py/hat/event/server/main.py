"""Event server main"""

from pathlib import Path
import asyncio
import contextlib
import importlib
import logging.config
import sys
import typing

import appdirs
import click

from hat import aio
from hat import json
from hat.event.server import common
import hat.event.server.backend_engine
import hat.event.server.communication
import hat.event.server.module_engine
import hat.monitor.client
import hat.monitor.common


mlog: logging.Logger = logging.getLogger('hat.event.server.main')
"""Module logger"""

user_conf_dir: Path = Path(appdirs.user_config_dir('hat'))
"""User configuration directory path"""


@click.command()
@click.option('--conf', default=None, metavar='PATH', type=Path,
              help="configuration defined by hat://event/main.yaml# "
                   "(default $XDG_CONFIG_HOME/hat/event.{yaml|yml|json})")
def main(conf: typing.Optional[Path]):
    """Event Server"""
    aio.init_asyncio()

    if not conf:
        for suffix in ('.yaml', '.yml', '.json'):
            conf = (user_conf_dir / 'event').with_suffix(suffix)
            if conf.exists():
                break
    conf = json.decode_file(conf)
    common.json_schema_repo.validate('hat://event/main.yaml#', conf)

    sub_confs = ([conf['backend_engine']['backend']] +
                 conf['module_engine']['modules'])
    for sub_conf in sub_confs:
        module = importlib.import_module(sub_conf['module'])
        if module.json_schema_repo and module.json_schema_id:
            module.json_schema_repo.validate(module.json_schema_id, sub_conf)

    logging.config.dictConfig(conf['log'])

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf))


async def async_main(conf: json.Data):
    """Async main entry point"""
    async_group = aio.Group()
    async_group.spawn(aio.call_on_cancel, asyncio.sleep, 0.1)

    try:
        monitor = await hat.monitor.client.connect(conf['monitor'])
        _bind_resource(async_group, monitor)

        backend_engine = await hat.event.server.backend_engine.create(
            conf['backend_engine'])
        _bind_resource(async_group, backend_engine)

        component = hat.monitor.client.Component(monitor, run, conf,
                                                 backend_engine)
        component.set_enabled(True)
        _bind_resource(async_group, component)

        await async_group.wait_closing()

    finally:
        await aio.uncancellable(async_group.async_close())


async def run(component: hat.monitor.client.Component,
              conf: json.Data,
              backend_engine: hat.event.server.backend_engine.BackendEngine):
    """Run monitor component"""
    async_group = aio.Group()

    try:
        module_engine = await hat.event.server.module_engine.create(
            conf['module_engine'], backend_engine)
        _bind_resource(async_group, module_engine)

        communication = await hat.event.server.communication.create(
            conf['communication'], module_engine)
        _bind_resource(async_group, communication)

        await async_group.wait_closing()

    finally:
        await aio.uncancellable(async_group.async_close())


def _bind_resource(async_group, resource):
    async_group.spawn(aio.call_on_cancel, resource.async_close)
    async_group.spawn(aio.call_on_done, resource.wait_closing(),
                      async_group.close)


if __name__ == '__main__':
    sys.argv[0] = 'hat-event'
    sys.exit(main())
