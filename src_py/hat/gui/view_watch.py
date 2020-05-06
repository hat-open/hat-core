# flake8: noqa

import logging
import base64
import json
import watchdog
import yaml

import hat.gui.vt
from hat import util


mlog = logging.getLogger(__name__)


View = util.namedtuple(
    'View',
    ['name', 'str'],
    ['conf', 'Any'],
    ['data', 'Dict[str,Any]'])


async def create_view_manager(conf, json_schema_repo):
    """Create view manager

    Args:
        conf (Any): configuration defined by
            ``hat://gui/main.yaml#/definitions/views``
        json_schema_repo (util.JsonSchemaRepository): json schema repository
            used for view configuration validation

    Returns:
        ViewManager

    """
    manager = ViewManager()
    manager._views = {view['name']: view for view in conf}
    manager._json_schema_repo = json_schema_repo
    manager._async_group = util.AsyncGroup()
    manager._executor = util.create_async_executor(1)


    return manager


class ViewManager:
    """View manager"""

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    async def get(self, name):
        """Get view

        Args:
            name (str): view name

        Returns:
            View

        """
        view = self._views[name]
        return await self._executor(_ext_get_view, view,
                                    self._json_schema_repo)


def _ext_get_view(view, json_schema_repo):
    with open(util.parse_env_path(view['conf']), encoding='utf-8') as f:
        conf = yaml.safe_load(f)
    if view['json_schema_id'] is not None:
        json_schema_repo.validate(view['json_schema_id'], conf)

    data = {}
    path = util.parse_env_path(view['path'])
    try:
        for i in path.rglob('*'):
            if i.is_dir():
                continue

            name = i.relative_to(path).as_posix()

            if i.suffix in {'.js', '.css', '.txt'}:
                with open(i, encoding='utf-8') as f:
                    content = f.read()
            elif i.suffix in {'.json'}:
                with open(i, encoding='utf-8') as f:
                    content = json.load(f)
            elif i.suffix in {'.yaml', '.yml'}:
                with open(i, encoding='utf-8') as f:
                    content = yaml.safe_load(f)
            elif i.suffix in {'.xml', '.svg'}:
                with open(i, encoding='utf-8') as f:
                    content = hat.gui.vt.parse(f)
            else:
                with open(i, 'rb') as f:
                    content = f.read()
                content = base64.b64encode(content).decode('utf-8')

            data[name] = content
    except Exception as e:
        mlog.error('error loading view data %s', e, exc_info=e)
        raise

    return View(name=view['name'],
                conf=conf,
                data=data)


async def create_views_repository(views):
    repo = ViewsRepository()
    repo._views = {}
    repo._observers = []
    executor = util.create_async_executor(1)
    for view in views:
        path = util.parse_env_path(view['path'])
        observer = watchdog.observers.Observer()
        observer.schedule(_Handler(view, repo._ext_on_change),
                          path, recursive=True)
        observer.start()
        repo._observers.append(observer)
        repo._views[view['name']] = await executor(_ext_get_view, view,
                                                   json_schema_repo)
    return repo


class _ObserverFactory:

    def __init__(self):
        self._observers = []

    async def observe(self, path, cb, recursive=False):
        observer = watchdog.observers.Observer()
        observer.start(_ExtHandler(ext_cb), path, recursive)
        self._observers.append(observer)

    async def async_close(self):
        executor = util.create_async_executor(1)
        await executor(_ext_stop_observers, self._observers)


def _ext_stop_observers(observers):
    for observer in observers:
        observer.stop()
    for observer in observers:
        observer.join()


_ExtHandler(watchdog.events.FileSystemEventHandler):

    def __init__(self, cb):
        self._cb = cb

    def on_any_event(self, event):
        self._cb(event)

def _start_observer(path, cb, recursive=False):
    observer = watchdog.observers.Observer()

    return observer


class ViewsRepository:

    async def get(self, name):
        return self._views[name]


    def close(self):
        for o in self._observers:
            o.stop()
        for o in self._observers:
            o.join()

    def _ext_on_change(view):
        self._views[view.name] = view


def _ext_watch(path):
    observer = watchdog.observers.Observer()
    handler = _Handler(path, lambda: print("change"))
    observer.schedule(handler, path, recursive=True)
    observer.run()


class _Handler(watchdog.events.FileSystemEventHandler):

    def __init__(self, path, load_cb):
        self._path = path

    def on_any_event(self, event):
        # data = _ext_load_view_data(self._path)
        # self._load_cb(data)
        self._load_cb("bobo")
