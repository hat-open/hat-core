"""View manager implementation"""

from pathlib import Path
import base64
import typing

from hat import aio
from hat import json
from hat import util
from hat.gui import vt


class View(typing.NamedTuple):
    """View data"""
    name: str
    conf: json.Data
    data: typing.Dict[str, json.Data]


async def create_view_manager(conf: json.Data
                              ) -> 'ViewManager':
    """Create view manager"""
    manager = ViewManager()
    manager._view_confs = {view_conf['name']: view_conf
                           for view_conf in conf['views']}
    manager._async_group = aio.Group()
    manager._executor = aio.create_executor()
    return manager


class ViewManager(aio.Resource):
    """View manager"""

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def get(self,
                  name: str
                  ) -> View:
        """Get view"""
        if not self.is_open:
            raise Exception('view manager is not open')

        conf = self._view_confs[name]
        view_path = Path(conf['view_path'])
        conf_path = Path(conf['conf_path']) if conf['conf_path'] else None
        return await self._async_group.spawn(self._executor, _ext_get_view,
                                             name, view_path, conf_path)


def _ext_get_view(name, view_path, conf_path):
    data = {}
    for i in view_path.rglob('*'):
        if i.is_dir():
            continue

        if i.suffix in {'.js', '.css', '.txt'}:
            with open(i, encoding='utf-8') as f:
                content = f.read()

        elif i.suffix in {'.json', '.yaml', '.yml'}:
            content = json.decode_file(i)

        elif i.suffix in {'.xml', '.svg'}:
            with open(i, encoding='utf-8') as f:
                content = vt.parse(f)

        else:
            with open(i, 'rb') as f:
                content = f.read()
            content = base64.b64encode(content).decode('utf-8')

        file_name = i.relative_to(view_path).as_posix()
        data[file_name] = content

    conf = json.decode_file(conf_path) if conf_path else None
    schema = util.first(v for k, v in data.items()
                        if k in {'schema.json', 'schema.yaml', 'schema.yml'})
    if schema:
        repo = json.SchemaRepository(schema)
        repo.validate(schema['id'], conf)

    return View(name=name,
                conf=conf,
                data=data)
