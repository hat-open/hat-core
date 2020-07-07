from pathlib import Path

from hat import asn1
from hat import sbs
from hat.util import json
import hat.sbs.generator


__all__ = ['task_schemas',
           'task_schemas_json',
           'task_schemas_sbs',
           'task_schemas_asn1',
           'task_schemas_json_util',
           'task_schemas_json_drivers',
           'task_schemas_json_orchestrator',
           'task_schemas_json_monitor',
           'task_schemas_json_event',
           'task_schemas_json_gateway',
           'task_schemas_json_gui',
           'task_schemas_json_syslog',
           'task_schemas_sbs_chat',
           'task_schemas_sbs_chatter',
           'task_schemas_sbs_monitor',
           'task_schemas_sbs_event',
           'task_schemas_asn1_copp',
           'task_schemas_asn1_acse',
           'task_schemas_asn1_mms']


schemas_json_dir = Path('schemas_json')
schemas_sbs_dir = Path('schemas_sbs')
schemas_asn1_dir = Path('schemas_asn1')
src_py_dir = Path('src_py')


def task_schemas():
    """Schemas - generate repository data"""
    return {'actions': None,
            'task_dep': ['schemas_json',
                         'schemas_sbs',
                         'schemas_asn1']}


def task_schemas_json():
    """Schemas - generate JSON schema repository data"""
    return {'actions': None,
            'task_dep': ['schemas_json_util',
                         'schemas_json_drivers',
                         'schemas_json_orchestrator',
                         'schemas_json_monitor',
                         'schemas_json_event',
                         'schemas_json_gateway',
                         'schemas_json_gui',
                         'schemas_json_syslog']}


def task_schemas_sbs():
    """Schemas - generate SBS repository data"""
    return {'actions': None,
            'task_dep': ['schemas_sbs_chat',
                         'schemas_sbs_chatter',
                         'schemas_sbs_monitor',
                         'schemas_sbs_event']}


def task_schemas_asn1():
    """Schemas - generate ASN.1 repository data"""
    return {'actions': None,
            'task_dep': ['schemas_asn1_copp',
                         'schemas_asn1_acse',
                         'schemas_asn1_mms']}


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


def task_schemas_json_syslog():
    """Schemas - generate hat-syslog JSON schema repository data"""
    return _get_task_json([schemas_json_dir / 'syslog.yaml'],
                          [src_py_dir / 'hat/syslog/json_schema_repo.json'])


def task_schemas_sbs_chat():
    """Schemas - generate CHat SBS .c and .h repository files"""
    src_paths = list(schemas_sbs_dir.rglob('*.sbs'))
    dst_dir = Path('src_c/hat')
    file_name = 'sbs_defs'
    dst_paths = [dst_dir / f'{file_name}.c',
                 dst_dir / f'{file_name}.h']

    def generate():
        repo = sbs.Repository(*src_paths)
        hat.sbs.generator.generate_c(repo, dst_dir, file_name)

    return {'actions': [generate],
            'file_dep': src_paths,
            'targets': dst_paths}


def task_schemas_sbs_chatter():
    """Schemas - generate hat-chatter SBS repository data"""
    return _get_task_sbs([schemas_sbs_dir / 'hat.sbs',
                          schemas_sbs_dir / 'hat/ping.sbs'],
                         [src_py_dir / 'hat/chatter/sbs_repo.json'])


def task_schemas_sbs_monitor():
    """Schemas - generate hat-monitor SBS repository data"""
    return _get_task_sbs([schemas_sbs_dir / 'hat/monitor.sbs'],
                         [src_py_dir / 'hat/monitor/sbs_repo.json'])


def task_schemas_sbs_event():
    """Schemas - generate hat-event SBS repository data"""
    return _get_task_sbs([schemas_sbs_dir / 'hat/event.sbs'],
                         [src_py_dir / 'hat/event/sbs_repo.json'])


def task_schemas_asn1_copp():
    """Schemas - generate COPP ASN.1 repository data"""
    return _get_task_asn1([schemas_asn1_dir / 'copp.asn'],
                          [src_py_dir / 'hat/drivers/copp/asn1_repo.json'])


def task_schemas_asn1_acse():
    """Schemas - generate ACSE ASN.1 repository data"""
    return _get_task_asn1([schemas_asn1_dir / 'acse.asn'],
                          [src_py_dir / 'hat/drivers/acse/asn1_repo.json'])


def task_schemas_asn1_mms():
    """Schemas - generate MMS ASN.1 repository data"""
    return _get_task_asn1([schemas_asn1_dir / 'mms.asn'],
                          [src_py_dir / 'hat/drivers/mms/asn1_repo.json'])


def _get_task_json(src_paths, dst_paths):

    def generate():
        repo = json.SchemaRepository(*src_paths)
        data = repo.to_json()
        for dst_path in dst_paths:
            json.encode_file(data, dst_path, indent=None)

    return {'actions': [generate],
            'file_dep': src_paths,
            'targets': dst_paths}


def _get_task_sbs(src_paths, dst_paths):

    def generate():
        repo = sbs.Repository(*src_paths)
        data = repo.to_json()
        for dst_path in dst_paths:
            json.encode_file(data, dst_path, indent=None)

    return {'actions': [generate],
            'file_dep': src_paths,
            'targets': dst_paths}


def _get_task_asn1(src_paths, dst_paths):

    def generate():
        repo = asn1.Repository(*src_paths)
        data = repo.to_json()
        for dst_path in dst_paths:
            json.encode_file(data, dst_path, indent=None)

    return {'actions': [generate],
            'file_dep': src_paths,
            'targets': dst_paths}
