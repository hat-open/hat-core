from pathlib import Path
import sys

import click
import PySide2.QtWebEngineWidgets
import PySide2.QtWidgets

from hat import aio
from hat import qt
from hat.drivers.manager.hue import server


package_path = Path(__file__).parent
default_ui_path = package_path / 'ui'


@click.command()
@click.option('--debug', default=False, is_flag=True,
              help='Show debugging console')
@click.option('--ui-path', default=default_ui_path, metavar='PATH', type=Path,
              help='Override web ui directory path (development argument)')
def main(debug, ui_path):
    return qt.run(async_main, debug, ui_path)


async def async_main(qt_executor, debug, ui_path):
    srv = await server.create(ui_path)
    await qt_executor(_ext_qt_open_window, srv.addr, debug)
    try:
        await srv.closed
    finally:
        aio.uncancellable(srv.async_close())


_ext_qt_view = None
_ext_qt_devtools_view = None


def _ext_qt_open_window(url, debug):
    global _view
    global _devtools_view

    _view = PySide2.QtWebEngineWidgets.QWebEngineView()
    _view.contextMenuEvent = lambda _: None
    _view.setWindowTitle('Hue manager')
    _view.load(url)
    _view.show()

    if debug:
        _devtools_view = PySide2.QtWebEngineWidgets.QWebEngineView()
        _devtools_view.page().setInspectedPage(_view.page())
        _devtools_view.show()


if __name__ == '__main__':
    sys.exit(main())
