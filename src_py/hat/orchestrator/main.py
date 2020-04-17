from pathlib import Path
import argparse
import asyncio
import contextlib
import logging.config
import sys

import appdirs

from hat import util
from hat.util import aio
from hat.util import json
import hat.orchestrator.component
import hat.orchestrator.ui


package_path = Path(__file__).parent
user_conf_dir = Path(appdirs.user_config_dir('hat'))

default_ui_path = package_path / 'ui'
default_conf_path = user_conf_dir / 'orchestrator.yaml'


def main():
    aio.init_asyncio()

    args = _create_parser().parse_args()
    conf = json.decode_file(args.conf)
    json_schema_repo = json.SchemaRepository(args.schemas_json_path)
    json_schema_repo.validate('hat://orchestrator.yaml#', conf)

    logging.config.dictConfig(conf['log'])

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf, args.ui_path))


async def async_main(conf, ui_path):
    components = [hat.orchestrator.component.Component(i)
                  for i in conf['components']]
    if not components:
        return
    ui = None
    try:
        ui = await hat.orchestrator.ui.create(conf['ui'], ui_path, components)
        wait_futures = [i.closed for i in components] + [ui.closed]
        await asyncio.wait(wait_futures, return_when=asyncio.FIRST_COMPLETED)
    finally:
        close_futures = [i.async_close() for i in components]
        if ui:
            close_futures.append(ui.async_close())
        await aio.uncancellable(asyncio.wait(close_futures),
                                raise_cancel=False)
        await aio.uncancellable(asyncio.sleep(0.1), raise_cancel=False)


def _create_parser():
    parser = argparse.ArgumentParser(prog='hat-orchestrator')
    parser.add_argument(
        '--conf', metavar='path', dest='conf',
        default=default_conf_path,
        action=util.EnvPathArgParseAction,
        help="configuration defined by hat://orchestrator.yaml# "
             "(default $XDG_CONFIG_HOME/hat/orchestrator.yaml)")

    dev_args = parser.add_argument_group('development arguments')
    dev_args.add_argument(
        '--json-schemas-path', metavar='path', dest='schemas_json_path',
        default=json.default_schemas_json_path,
        action=util.EnvPathArgParseAction,
        help="override json schemas directory path")
    dev_args.add_argument(
        '--ui-path', metavar='path', dest='ui_path',
        default=default_ui_path,
        action=util.EnvPathArgParseAction,
        help="override web ui directory path")
    return parser


if __name__ == '__main__':
    sys.exit(main())
