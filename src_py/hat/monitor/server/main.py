"""Monitor server main"""

from pathlib import Path
import argparse
import asyncio
import contextlib
import logging.config
import sys

import appdirs

from hat import sbs
from hat import util
from hat.monitor import common
from hat.util import aio
from hat.util import json
import hat.monitor.server.master
import hat.monitor.server.server
import hat.monitor.server.ui


package_path = Path(__file__).parent
user_conf_dir = Path(appdirs.user_config_dir('hat'))

default_ui_path = package_path / 'ui'
default_conf_path = user_conf_dir / 'monitor.yaml'


def main():
    aio.init_asyncio()

    args = _create_parser().parse_args()
    conf = json.decode_file(args.conf)
    json_schema_repo = json.SchemaRepository(args.schemas_json_path)
    json_schema_repo.validate('hat://monitor/main.yaml#', conf)

    logging.config.dictConfig(conf['log'])

    sbs_repo = common.create_sbs_repo(args.schemas_sbs_path)

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf, sbs_repo, args.ui_path))


async def async_main(conf, sbs_repo, ui_path):
    async_group = aio.Group()
    server = await hat.monitor.server.server.create(conf['server'], sbs_repo)
    master_run_future = async_group.spawn(
        hat.monitor.server.master.run, conf['master'], sbs_repo,
        server.set_master)
    ui = None
    try:
        ui = await hat.monitor.server.ui.create(conf['ui'], ui_path, server)
        wait_futures = [server.closed, master_run_future, ui.closed]
        await asyncio.wait(wait_futures, return_when=asyncio.FIRST_COMPLETED)
    finally:
        close_futures = [server.async_close(), async_group.async_close()]
        if ui:
            close_futures.append(ui.async_close())
        await aio.uncancellable(asyncio.wait(close_futures),
                                raise_cancel=False)
        await aio.uncancellable(asyncio.sleep(0.1), raise_cancel=False)


def _create_parser():
    parser = argparse.ArgumentParser(prog='hat-monitor')
    parser.add_argument(
        '--conf', metavar='path', dest='conf',
        default=default_conf_path,
        action=util.EnvPathArgParseAction,
        help="configuration defined by hat://monitor/main.yaml# "
             "(default $XDG_CONFIG_HOME/hat/monitor.yaml)")

    dev_args = parser.add_argument_group('development arguments')
    dev_args.add_argument(
        '--json-schemas-path', metavar='path', dest='schemas_json_path',
        default=json.default_schemas_json_path,
        action=util.EnvPathArgParseAction,
        help="override json schemas directory path")
    dev_args.add_argument(
        '--sbs-schemas-path', metavar='path', dest='schemas_sbs_path',
        default=sbs.default_schemas_sbs_path,
        action=util.EnvPathArgParseAction,
        help="override sbs schemas directory path")
    dev_args.add_argument(
        '--ui-path', metavar='path', dest='ui_path',
        default=default_ui_path,
        action=util.EnvPathArgParseAction,
        help="override web ui directory path")
    return parser


if __name__ == '__main__':
    sys.exit(main())
