from pathlib import Path
import asyncio
import contextlib
import sys

import click

from hat import aio
from hat.manager.iec104.server import create_server


package_path = Path(__file__).parent
default_ui_path = package_path / 'ui'


@click.command()
@click.option('--host', default='127.0.0.1',
              help='UI listening host')
@click.option('--port', default=23024, type=int,
              help='UI listening port')
@click.option('--ui-path', default=default_ui_path, metavar='PATH', type=Path,
              help='Override web ui directory path (development argument)')
def main(host, port, ui_path):
    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(host, port, ui_path))


async def async_main(host, port, ui_path):
    srv = await create_server(host, port, ui_path)
    try:
        await srv.wait_closing()
    finally:
        await aio.uncancellable(srv.async_close())


if __name__ == '__main__':
    sys.exit(main())
