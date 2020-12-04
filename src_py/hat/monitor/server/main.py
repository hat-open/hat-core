"""Monitor server main"""

from pathlib import Path
import argparse
import asyncio
import contextlib
import logging.config
import sys

import appdirs

from hat import aio
from hat import json
from hat.monitor import common
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
    common.json_schema_repo.validate('hat://monitor/main.yaml#', conf)

    logging.config.dictConfig(conf['log'])

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf, args.ui_path))


async def async_main(conf, ui_path):
    async_group = aio.Group()
    server = await hat.monitor.server.server.create(conf['server'])
    master_run_future = async_group.spawn(
        hat.monitor.server.master.run, conf['master'], server.set_master)
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
        default=default_conf_path, type=Path,
        help="configuration defined by hat://monitor/main.yaml# "
             "(default $XDG_CONFIG_HOME/hat/monitor.yaml)")

    dev_args = parser.add_argument_group('development arguments')
    dev_args.add_argument(
        '--ui-path', metavar='path', dest='ui_path',
        default=default_ui_path, type=Path,
        help="override web ui directory path")
    return parser


if __name__ == '__main__':
    sys.exit(main())
