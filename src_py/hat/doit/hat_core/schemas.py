from pathlib import Path

from hat.util import json


__all__ = ['task_schemas',
           'task_schemas_json',
           'task_schemas_json_util',
           'task_schemas_json_drivers',
           'task_schemas_json_orchestrator',
           'task_schemas_json_monitor',
           'task_schemas_json_event',
           'task_schemas_json_gateway',
           'task_schemas_json_gui']


schemas_json_dir = Path('schemas_json')
src_py_dir = Path('src_py')


def task_schemas():
    """Schemas - generate schema repository data"""
    return {'actions': None,
            'task_dep': ['schemas_json']}


def task_schemas_json():
    """Schemas - generate JSON schema repository data"""
    return {'actions': None,
            'task_dep': ['schemas_json_util',
                         'schemas_json_drivers',
                         'schemas_json_orchestrator',
                         'schemas_json_monitor',
                         'schemas_json_event',
                         'schemas_json_gateway',
                         'schemas_json_gui']}


def task_schemas_json_util():
    """Schemas - generate hat-util JSON schema repository data"""
    return _get_task_json([schemas_json_dir / 'logging.yaml'],
                          [src_py_dir / 'hat/util/json_schema_repo.json'])


def task_schemas_json_drivers():
    """Schemas - generate hat-drivers JSON schema repository data"""
    return _get_task_json([*(schemas_json_dir / 'drivers').rglob('*.yaml')],
                          [src_py_dir / 'hat/drivers/json_schema_repo.json'])


def task_schemas_json_orchestrator():
    """Schemas - generate hat-orchestrator JSON schema repository data"""
    return _get_task_json(
        [schemas_json_dir / 'orchestrator.yaml'],
        [src_py_dir / 'hat/orchestrator/json_schema_repo.json'])


def task_schemas_json_monitor():
    """Schemas - generate hat-monitor JSON schema repository data"""
    return _get_task_json([*(schemas_json_dir / 'monitor').rglob('*.yaml')],
                          [src_py_dir / 'hat/monitor/json_schema_repo.json'])


def task_schemas_json_event():
    """Schemas - generate hat-event JSON schema repository data"""
    return _get_task_json([*(schemas_json_dir / 'event').rglob('*.yaml')],
                          [src_py_dir / 'hat/event/json_schema_repo.json'])


def task_schemas_json_gateway():
    """Schemas - generate hat-gateway JSON schema repository data"""
    return _get_task_json([*(schemas_json_dir / 'gateway').rglob('*.yaml')],
                          [src_py_dir / 'hat/gateway/json_schema_repo.json'])


def task_schemas_json_gui():
    """Schemas - generate hat-gui JSON schema repository data"""
    return _get_task_json([*(schemas_json_dir / 'gui').rglob('*.yaml')],
                          [src_py_dir / 'hat/gui/json_schema_repo.json'])


def _get_task_json(src_paths, dst_paths):

    def generate():
        repo = json.SchemaRepository(*src_paths)
        data = repo.to_json()
        for dst_path in dst_paths:
            json.encode_file(data, dst_path, indent=None)

    return {'actions': [generate],
            'file_dep': src_paths,
            'targets': dst_paths}
