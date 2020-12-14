"""Orchestrator main"""

from pathlib import Path
import argparse
import asyncio
import contextlib
import logging.config
import sys

import appdirs

from hat import aio
from hat import json
import hat.orchestrator.component
import hat.orchestrator.ui


package_path: Path = Path(__file__).parent
"""Package file system path"""

user_conf_dir: Path = Path(appdirs.user_config_dir('hat'))
"""User configuration directory"""

default_ui_path: Path = package_path / 'ui'
"""Default UI file system path"""

default_conf_path: Path = user_conf_dir / 'orchestrator.yaml'
"""Default configuration file system path"""

json_schema_repo: json.SchemaRepository = json.SchemaRepository(
    json.json_schema_repo,
    json.SchemaRepository.from_json(package_path / 'json_schema_repo.json'))
"""JSON schema repository"""


def main():
    """Main"""
    aio.init_asyncio()

    args = _create_parser().parse_args()
    conf = json.decode_file(args.conf)
    json_schema_repo.validate('hat://orchestrator.yaml#', conf)

    logging.config.dictConfig(conf['log'])

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf, args.ui_path))


async def async_main(conf: json.Data, ui_path: Path):
    """Async main"""
    async_group = aio.Group()
    components = []

    try:
        for component_conf in conf['components']:
            component = hat.orchestrator.component.Component(component_conf)
            async_group.spawn(aio.call_on_cancel, component.async_close)
            async_group.spawn(aio.call_on_done, component.wait_closed(),
                              async_group.close)
            components.append(component)

        ui = await hat.orchestrator.ui.create(conf['ui'], ui_path, components)
        async_group.spawn(aio.call_on_cancel, ui.async_close)
        async_group.spawn(aio.call_on_done, ui.wait_closed(),
                          async_group.close)

        await async_group.wait_closed()

    finally:
        await aio.uncancellable(async_group.async_close(), raise_cancel=False)
        await aio.uncancellable(asyncio.sleep(0.1), raise_cancel=False)


def _create_parser():
    parser = argparse.ArgumentParser(prog='hat-orchestrator')
    parser.add_argument(
        '--conf', metavar='path', dest='conf',
        default=default_conf_path, type=Path,
        help="configuration defined by hat://orchestrator.yaml# "
             "(default $XDG_CONFIG_HOME/hat/orchestrator.yaml)")

    dev_args = parser.add_argument_group('development arguments')
    dev_args.add_argument(
        '--ui-path', metavar='path', dest='ui_path',
        default=default_ui_path, type=Path,
        help="override web ui directory path")
    return parser


if __name__ == '__main__':
    sys.exit(main())
