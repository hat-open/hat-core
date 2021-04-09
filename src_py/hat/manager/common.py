from pathlib import Path
import abc
import typing

from hat import aio
from hat import json
from hat import util


package_path: Path = Path(__file__).parent
"""Python package path"""

json_schema_repo: json.SchemaRepository = json.SchemaRepository(
    json.json_schema_repo,
    json.SchemaRepository.from_json(package_path / 'json_schema_repo.json'))
"""JSON schema repository"""


def get_log_conf(settings: json.Data) -> json.Data:
    """Generate log configuration"""
    handlers = []

    if settings['log']['syslog']['enabled']:
        handlers.append('syslog')

    if settings['log']['console']['enabled']:
        handlers.append('console')

    return {
        'version': 1,
        'formatters': {
            'syslog': {},
            'console': {
                'format': "[%(asctime)s %(levelname)s %(name)s] %(message)s"}},
        'handlers': {
            'syslog': {
                'class': 'hat.syslog.handler.SysLogHandler',
                'host': settings['log']['syslog']['host'],
                'port': settings['log']['syslog']['port'],
                'comm_type': 'TCP',
                'level': 'DEBUG',
                'formatter': 'syslog',
                'queue_size': 10},
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'console',
                'level': 'DEBUG'}},
        'loggers': {
            'hat': {
                'level': settings['log']['level']}},
        'root': {
            'level': settings['log']['level'],
            'handlers': handlers},
        'disable_existing_loggers': False}


default_settings: json.Data = {'ui': {'address': 'http://127.0.0.1:23024'},
                               'log': {'level': 'INFO',
                                       'syslog': {'enabled': False,
                                                  'host': '127.0.0.1',
                                                  'port': 6514},
                                       'console': {'enabled': False}}}
"""Default settings"""

default_conf: json.Data = {
    'type': 'manager',
    'log': get_log_conf(default_settings),
    'settings': default_settings,
    'devices': []}
"""Default configuration"""


class Logger:
    """Message logger"""

    def __init__(self):
        self._log_cbs = util.CallbackRegistry()

    def log(self, msg: str):
        """Log message"""
        self._log_cbs.notify(msg)

    def register_log_cb(self,
                        cb: typing.Callable[[str], None]
                        ) -> util.RegisterCallbackHandle:
        """Register log callback"""
        return self._log_cbs.register(cb)


class DataStorage:
    """Data storage"""

    def __init__(self, data: json.Data = None):
        self._data = data
        self._change_cbs = util.CallbackRegistry()

    @property
    def data(self) -> json.Data:
        """Data"""
        return self._data

    def register_change_cb(self,
                           cb: typing.Callable[[json.Data], None]
                           ) -> util.RegisterCallbackHandle:
        """Register data change callback"""
        return self._change_cbs.register(cb)

    def set(self, path: json.Path, value: json.Data):
        """Set data"""
        self._data = json.set_(self._data, path, value)
        self._change_cbs.notify(self._data)

    def remove(self, path: json.Path):
        """Remove data"""
        self._data = json.remove(self._data, path)
        self._change_cbs.notify(self._data)


class Device(abc.ABC):
    """Abstract device interface"""

    @property
    @abc.abstractmethod
    def data(self) -> DataStorage:
        """Local data"""

    @abc.abstractmethod
    def get_conf(self) -> json.Data:
        """Get configuration"""

    @abc.abstractmethod
    async def create(self) -> aio.Resource:
        """Create running resource"""

    @abc.abstractmethod
    async def execute(self,
                      action: str,
                      *args: json.Data
                      ) -> json.Data:
        """Execute action"""
