from pathlib import Path
import sys

import click
import PySide2.QtWebEngineWidgets
import PySide2.QtWidgets

from hat import aio
from hat import qt
from hat.manager.event import server


package_path = Path(__file__).parent
default_ui_path = package_path / 'ui'


@click.command()
@click.option('--addr', metavar='URL',
              default='tcp+sbs://127.0.0.1:23012', show_default=True,
              help='Event Server address')
@click.option('--debug', default=False, is_flag=True,
              help='Show debugging console')
@click.option('--ui-path', default=default_ui_path, metavar='PATH', type=Path,
              help='Override web ui directory path (development argument)')
def main(addr, debug, ui_path):
    return qt.run(async_main, addr, debug, ui_path)


async def async_main(qt_executor, addr, debug, ui_path):
    srv = await server.create(addr, ui_path)
    await qt_executor(_ext_qt_open_window, srv.addr, debug)
    try:
        await srv.wait_closed()
    finally:
        aio.uncancellable(srv.async_close())


_ext_qt_view = None
_ext_qt_devtools_view = None


def _ext_qt_open_window(url, debug):
    global _view
    global _devtools_view

    _view = PySide2.QtWebEngineWidgets.QWebEngineView()
    _view.contextMenuEvent = lambda _: None
    _view.setWindowTitle('Event Viewer')
    _view.load(url)
    _view.show()

    if debug:
        _devtools_view = PySide2.QtWebEngineWidgets.QWebEngineView()
        _devtools_view.page().setInspectedPage(_view.page())
        _devtools_view.show()


if __name__ == '__main__':
    sys.exit(main())
