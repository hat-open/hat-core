from pathlib import Path
import base64
import logging

from hat import aio
from hat import json
from hat import util
import hat.gui.vt


mlog = logging.getLogger(__name__)


View = util.namedtuple(
    'View',
    ['name', 'str'],
    ['conf', 'json.Data'],
    ['data', 'Dict[str,json.Data]'])


async def create_view_manager(conf, json_schema_repo):
    """Create view manager

    Args:
        conf (json.Data): configuration defined by
            ``hat://gui/main.yaml#/definitions/views``
        json_schema_repo (json.SchemaRepository): json schema repository
            used for view configuration validation

    Returns:
        ViewManager

    """
    manager = ViewManager()
    manager._views = {view['name']: view for view in conf}
    manager._json_schema_repo = json_schema_repo
    manager._async_group = aio.Group()
    manager._executor = aio.create_executor(1)
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
        if self.closed.done():
            raise Exception('view manager is closed')
        view = self._views[name]
        return await self._async_group.spawn(self._executor, _ext_get_view,
                                             view, self._json_schema_repo)


def _ext_get_view(view, json_schema_repo):
    data = {}
    view_path = Path(view['view_path'])
    try:
        for i in view_path.rglob('*'):
            if i.is_dir():
                continue

            name = i.relative_to(view_path).as_posix()

            if i.suffix in {'.js', '.css', '.txt'}:
                with open(i, encoding='utf-8') as f:
                    content = f.read()
            elif i.suffix in {'.json', '.yaml', '.yml'}:
                content = json.decode_file(i)
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

    conf = None
    if view['conf_path'] is not None:
        conf_path = Path(view['conf_path'])
        conf = json.decode_file(conf_path)
    schema = util.first(v for k, v in data.items()
                        if k in {'schema.json', 'schema.yaml', 'schema.yml'})
    if schema:
        repo = json.SchemaRepository(json_schema_repo, schema)
        repo.validate(schema['id'], conf)

    return View(name=view['name'],
                conf=conf,
                data=data)
