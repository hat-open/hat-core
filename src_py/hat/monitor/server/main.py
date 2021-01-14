"""Monitor server main"""

from pathlib import Path
import asyncio
import contextlib
import logging.config
import sys

import appdirs
import click

from hat import aio
from hat import json
from hat.monitor.server import common
import hat.monitor.server.master
import hat.monitor.server.server
import hat.monitor.server.slave
import hat.monitor.server.ui


mlog: logging.Logger = logging.getLogger('hat.monitor.server.main')
"""Module logger"""

package_path: Path = Path(__file__).parent
"""Python package path"""

user_conf_dir: Path = Path(appdirs.user_config_dir('hat'))
"""User configuration directory path"""

default_ui_path: Path = package_path / 'ui'
"""Default web ui directory path"""

default_conf_path: Path = user_conf_dir / 'monitor.yaml'
"""Default configuration file path"""


@click.command()
@click.option('--conf', default=default_conf_path, metavar='PATH', type=Path,
              help="configuration defined by hat://monitor/main.yaml# "
                   "(default $XDG_CONFIG_HOME/hat/monitor.yaml)")
@click.option('--ui-path', default=default_ui_path, metavar='PATH', type=Path,
              help="Override web ui directory path (development argument)")
def main(conf: Path,
         ui_path: Path):
    """Main entry point"""
    aio.init_asyncio()

    conf = json.decode_file(conf)
    common.json_schema_repo.validate('hat://monitor/main.yaml#', conf)

    logging.config.dictConfig(conf['log'])

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf, ui_path))


async def async_main(conf: json.Data,
                     ui_path: Path):
    """Async main entry point"""
    async_group = aio.Group()
    async_group.spawn(aio.call_on_cancel, asyncio.sleep, 0.1)

    try:
        mlog.debug('starting server')
        server = await hat.monitor.server.server.create(conf['server'])
        async_group.spawn(aio.call_on_cancel, server.async_close)

        mlog.debug('starting master')
        master = await hat.monitor.server.master.create(conf['master'])
        async_group.spawn(aio.call_on_cancel, master.async_close)

        mlog.debug('starting ui')
        ui = await hat.monitor.server.ui.create(conf['ui'], ui_path, server)
        async_group.spawn(aio.call_on_cancel, ui.async_close)

        mlog.debug('starting slave')
        slave_future = async_group.spawn(hat.monitor.server.slave.run,
                                         conf['slave'], server, master)

        mlog.debug('monitor started')
        for f in [server.wait_closing(),
                  master.wait_closing(),
                  ui.wait_closing(),
                  slave_future]:
            async_group.spawn(aio.call_on_done, f, async_group.close)

        await async_group.wait_closing()

    except Exception as e:
        mlog.warning('async main error: %s', e, exc_info=e)

    finally:
        mlog.debug('stopping monitor')
        await aio.uncancellable(async_group.async_close())


if __name__ == '__main__':
    sys.exit(main())
