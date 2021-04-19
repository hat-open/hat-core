"""Orchestrator main"""

from pathlib import Path
import asyncio
import contextlib
import logging.config
import sys
import typing

import appdirs
import click

from hat import aio
from hat import json
import hat.orchestrator.component
import hat.orchestrator.process
import hat.orchestrator.ui


package_path: Path = Path(__file__).parent
"""Package file system path"""

user_conf_dir: Path = Path(appdirs.user_config_dir('hat'))
"""User configuration directory"""

default_ui_path: Path = package_path / 'ui'
"""Default UI file system path"""

json_schema_repo: json.SchemaRepository = json.SchemaRepository(
    json.json_schema_repo,
    json.SchemaRepository.from_json(package_path / 'json_schema_repo.json'))
"""JSON schema repository"""


@click.command()
@click.option('--conf', default=None, metavar='PATH', type=Path,
              help="configuration defined by hat://orchestrator.yaml# "
                   "(default $XDG_CONFIG_HOME/hat/orchestrator.{yaml|yml|json})")  # NOQA
@click.option('--ui-path', default=default_ui_path, metavar='PATH', type=Path,
              help="Override web ui directory path (development argument)")
def main(conf: typing.Optional[Path],
         ui_path: Path):
    """Orchestrator"""
    aio.init_asyncio()

    if not conf:
        for suffix in ('.yaml', '.yml', '.json'):
            conf = (user_conf_dir / 'orchestrator').with_suffix(suffix)
            if conf.exists():
                break
    conf = json.decode_file(conf)
    json_schema_repo.validate('hat://orchestrator.yaml#', conf)

    logging.config.dictConfig(conf['log'])

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf, ui_path))


async def async_main(conf: json.Data,
                     ui_path: Path):
    """Async main"""
    async_group = aio.Group()
    async_group.spawn(aio.call_on_cancel, asyncio.sleep, 0.1)

    try:
        if sys.platform == 'win32':
            win32_job = hat.orchestrator.process.Win32Job()
            _bind_resource(async_group, win32_job)
        else:
            win32_job = None

        components = []
        for component_conf in conf['components']:
            component = hat.orchestrator.component.Component(component_conf,
                                                             win32_job)
            _bind_resource(async_group, component)
            components.append(component)

        ui = await hat.orchestrator.ui.create(conf['ui'], ui_path, components)
        _bind_resource(async_group, ui)

        await async_group.wait_closing()

    finally:
        await aio.uncancellable(async_group.async_close())


def _bind_resource(async_group, resource):
    async_group.spawn(aio.call_on_cancel, resource.async_close)
    async_group.spawn(aio.call_on_done, resource.wait_closing(),
                      async_group.close)


if __name__ == '__main__':
    sys.argv[0] = 'hat-orchestrator'
    sys.exit(main())
