from pathlib import Path
import subprocess
import sys

from hat.doit import common

from .jshat.lib import build_dir as jshat_dir
from .pyhat import build_dir as pyhat_dir


__all__ = ['task_dist',
           'task_dist_upload',
           'task_dist_pyhat_util',
           'task_dist_pyhat_aio',
           'task_dist_pyhat_json',
           'task_dist_pyhat_qt',
           'task_dist_pyhat_peg',
           'task_dist_pyhat_stc',
           'task_dist_pyhat_sbs',
           'task_dist_pyhat_chatter',
           'task_dist_pyhat_juggler',
           'task_dist_pyhat_duktape',
           'task_dist_pyhat_sqlite3',
           'task_dist_pyhat_asn1',
           'task_dist_pyhat_drivers',
           'task_dist_pyhat_syslog',
           'task_dist_pyhat_orchestrator',
           'task_dist_pyhat_monitor',
           'task_dist_pyhat_event',
           'task_dist_pyhat_gateway',
           'task_dist_pyhat_gui',
           'task_dist_pyhat_manager',
           'task_dist_jshat_util',
           'task_dist_jshat_renderer',
           'task_dist_jshat_future',
           'task_dist_jshat_juggler']


dist_dir = Path('dist')
dist_py_dir = dist_dir / 'pip'
dist_js_dir = dist_dir / 'npm'


def task_dist():
    """Dist - create all distribution packages"""
    return {'actions': None,
            'task_dep': ['dist_pyhat_util',
                         'dist_pyhat_aio',
                         'dist_pyhat_json',
                         'dist_pyhat_qt',
                         'dist_pyhat_peg',
                         'dist_pyhat_stc',
                         'dist_pyhat_sbs',
                         'dist_pyhat_chatter',
                         'dist_pyhat_juggler',
                         'dist_pyhat_duktape',
                         'dist_pyhat_sqlite3',
                         'dist_pyhat_asn1',
                         'dist_pyhat_drivers',
                         'dist_pyhat_syslog',
                         'dist_pyhat_orchestrator',
                         'dist_pyhat_monitor',
                         'dist_pyhat_event',
                         'dist_pyhat_gateway',
                         'dist_pyhat_gui',
                         'dist_pyhat_manager',
                         'dist_jshat_util',
                         'dist_jshat_renderer',
                         'dist_jshat_future',
                         'dist_jshat_juggler']}


def task_dist_upload():
    """Dist - upload packages"""
    def upload():
        pass

    return {'actions': [upload],
            'task_dep': ['dist']}


def task_dist_pyhat_util():
    """Dist - create pyhat hat-util distribution"""
    return _get_task_dist_pyhat('hat-util', 'pyhat_util')


def task_dist_pyhat_aio():
    """Dist - create pyhat hat-aio distribution"""
    return _get_task_dist_pyhat('hat-aio', 'pyhat_aio')


def task_dist_pyhat_json():
    """Dist - create pyhat hat-json distribution"""
    return _get_task_dist_pyhat('hat-json', 'pyhat_json')


def task_dist_pyhat_qt():
    """Dist - create pyhat hat-qt distribution"""
    return _get_task_dist_pyhat('hat-qt', 'pyhat_qt')


def task_dist_pyhat_peg():
    """Dist - create pyhat hat-peg distribution"""
    return _get_task_dist_pyhat('hat-peg', 'pyhat_peg')


def task_dist_pyhat_stc():
    """Dist - create pyhat hat-stc distribution"""
    return _get_task_dist_pyhat('hat-stc', 'pyhat_stc')


def task_dist_pyhat_sbs():
    """Dist - create pyhat hat-sbs distribution"""
    return _get_task_dist_pyhat('hat-sbs', 'pyhat_sbs')


def task_dist_pyhat_chatter():
    """Dist - create pyhat hat-chatter distribution"""
    return _get_task_dist_pyhat('hat-chatter', 'pyhat_chatter')


def task_dist_pyhat_juggler():
    """Dist - create pyhat hat-juggler distribution"""
    return _get_task_dist_pyhat('hat-juggler', 'pyhat_juggler')


def task_dist_pyhat_duktape():
    """Dist - create pyhat hat-duktape distribution"""
    return _get_task_dist_pyhat('hat-duktape', 'pyhat_duktape')


def task_dist_pyhat_sqlite3():
    """Dist - create pyhat hat-sqlite3 distribution"""
    return _get_task_dist_pyhat('hat-sqlite3', 'pyhat_sqlite3')


def task_dist_pyhat_asn1():
    """Dist - create pyhat hat-asn1 distribution"""
    return _get_task_dist_pyhat('hat-asn1', 'pyhat_asn1')


def task_dist_pyhat_drivers():
    """Dist - create pyhat hat-drivers distribution"""
    return _get_task_dist_pyhat('hat-drivers', 'pyhat_drivers')


def task_dist_pyhat_syslog():
    """Dist - create pyhat hat-syslog distribution"""
    return _get_task_dist_pyhat('hat-syslog', 'pyhat_syslog')


def task_dist_pyhat_orchestrator():
    """Dist - create pyhat hat-orchestrator distribution"""
    return _get_task_dist_pyhat('hat-orchestrator', 'pyhat_orchestrator')


def task_dist_pyhat_monitor():
    """Dist - create pyhat hat-monitor distribution"""
    return _get_task_dist_pyhat('hat-monitor', 'pyhat_monitor')


def task_dist_pyhat_event():
    """Dist - create pyhat hat-event distribution"""
    return _get_task_dist_pyhat('hat-event', 'pyhat_event')


def task_dist_pyhat_gateway():
    """Dist - create pyhat hat-gateway distribution"""
    return _get_task_dist_pyhat('hat-gateway', 'pyhat_gateway')


def task_dist_pyhat_gui():
    """Dist - create pyhat hat-gui distribution"""
    return _get_task_dist_pyhat('hat-gui', 'pyhat_gui')


def task_dist_pyhat_manager():
    """Dist - create pyhat hat-manager distribution"""
    return _get_task_dist_pyhat('hat-manager', 'pyhat_manager')


def task_dist_jshat_util():
    """Dist - create jshat @hat-core/util distribution"""
    return _get_task_dist_jshat('@hat-core/util', 'jshat_lib_util')


def task_dist_jshat_renderer():
    """Dist - create jshat @hat-core/renderer distribution"""
    return _get_task_dist_jshat('@hat-core/renderer', 'jshat_lib_renderer')


def task_dist_jshat_future():
    """Dist - create jshat @hat-core/future distribution"""
    return _get_task_dist_jshat('@hat-core/future', 'jshat_lib_future')


def task_dist_jshat_juggler():
    """Dist - create jshat @hat-core/juggler distribution"""
    return _get_task_dist_jshat('@hat-core/juggler', 'jshat_lib_juggler')


def _get_task_dist_pyhat(name, build_task):
    src_path = pyhat_dir / name
    dst_path = dist_py_dir / name
    return {'actions': [(common.mkdir_p, [dst_path]),
                        (_create_wheel, [src_path, dst_path])],
            'task_dep': [build_task]}


def _get_task_dist_jshat(name, build_task):
    src_path = jshat_dir / name
    dst_path = dist_js_dir
    return {'actions': [(common.mkdir_p, [dst_path]),
                        (_create_npm_package, [src_path, dst_path])],
            'task_dep': [build_task]}


def _create_wheel(src_path, dst_path):
    subprocess.run([sys.executable, 'setup.py', '-q', 'bdist_wheel',
                    '--dist-dir', str(dst_path.resolve())],
                   cwd=str(src_path),
                   check=True)


def _create_npm_package(src_path, dst_path):
    subprocess.run(['npm', 'pack', '--silent', str(src_path.resolve())],
                   stdout=subprocess.DEVNULL,
                   cwd=str(dst_path),
                   check=True)
