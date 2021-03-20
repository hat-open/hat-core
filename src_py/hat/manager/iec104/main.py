from pathlib import Path
import signal
import subprocess
import sys

import click
import PySide2.QtWebEngineWidgets
import PySide2.QtWidgets

from hat import aio
from hat import juggler
from hat import qt
from hat import util
from hat.manager.iec104.client import Client


package_path = Path(__file__).parent
default_ui_path = package_path / 'ui'


@click.command()
@click.option('--browser', default=False, is_flag=True,
              help='Open in external browser')
@click.option('--debug', default=False, is_flag=True,
              help='Show debugging console')
@click.option('--ui-path', default=default_ui_path, metavar='PATH', type=Path,
              help='Override web ui directory path (development argument)')
def main(browser, debug, ui_path):
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return qt.run(async_main, browser, debug, ui_path)


async def async_main(qt_executor, browser, debug, ui_path):
    port = util.get_unused_tcp_port()
    addr = f'http://127.0.0.1:{port}'

    srv = await juggler.listen('127.0.0.1', port, Client, static_dir=ui_path)

    if browser:
        subprocess.Popen(['xdg-open', addr])
    else:
        await qt_executor(_ext_qt_open_window, addr, debug)

    try:
        await srv.wait_closed()
    finally:
        await aio.uncancellable(srv.async_close())


_ext_qt_view = None
_ext_qt_devtools_view = None


def _ext_qt_open_window(url, debug):
    global _view
    global _devtools_view

    _view = PySide2.QtWebEngineWidgets.QWebEngineView()
    _view.contextMenuEvent = lambda _: None
    _view.setWindowTitle('IEC104 Manager')
    _view.load(url)
    _view.show()

    if debug:
        _devtools_view = PySide2.QtWebEngineWidgets.QWebEngineView()
        _devtools_view.page().setInspectedPage(_view.page())
        _devtools_view.show()


if __name__ == '__main__':
    sys.exit(main())
