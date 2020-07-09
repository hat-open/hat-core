import json
from pathlib import Path

from PySide2.QtCore import QObject, Slot, Property
from PySide2.QtWidgets import QFileDialog
from PySide2.QtWebEngineWidgets import QWebEngineView
from PySide2.QtWebChannel import QWebChannel

from hat.peg_browser import parser


_refs = {}


def create(ui_path, proxy):

    view = QWebEngineView()
    page = view.page()

    channel = QWebChannel()
    channel.registerObject('hatPegBrowserProxy', proxy)
    page.setWebChannel(channel)

    view.load(str((ui_path / 'index.html').resolve().as_uri()))
    view.show()

    _refs[view] = (channel, proxy)
    # TODO: release references when window is closed


class MainProxy(QObject):

    type = Property(str, lambda self: 'main', constant=True)

    def __init__(self, ui_path, fonts_path):
        super().__init__()
        self._ui_path = ui_path
        self._fonts_path = fonts_path
        self._view = None

    @Slot(result='QVariant')
    def act_open(self):
        path, _ = QFileDialog.getOpenFileName()
        if not path:
            return
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return dict(data, saveFilePath=path)

    @Slot('QVariant', result=str)
    def act_save(self, state):
        if state['saveFilePath']:
            path = Path(state['saveFilePath'])
        else:
            path, _ = QFileDialog.getSaveFileName()
        return _save(path, state)

    @Slot('QVariant', result=str)
    def act_save_as(self, state):
        path, _ = QFileDialog.getSaveFileName()
        return _save(path, state)

    @Slot('QVariant')
    def act_parse(self, state):
        data = parser.parse(fonts_path=self._fonts_path,
                            definitions=state['definitions']['value'],
                            starting=state['starting'],
                            delimiter=state['delimiter'],
                            data=state['data']['value'])
        browser_proxy = BrowserProxy(data)
        create(self._ui_path, browser_proxy)


class BrowserProxy(QObject):

    type = Property(str, lambda self: 'browser', constant=True)
    data = Property('QVariant', lambda self: self._data, constant=True)

    def __init__(self, data):
        super().__init__()
        self._data = data


def _save(path, state):
    if not path:
        return
    state = dict(state, saveFilePath=None)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f)
    return str(path)
