from pathlib import Path
import subprocess

from hat.doit import common
from hat.doit.hat_core.pyhat import build_dir as pyhat_dir


__all__ = ['task_dist',
           'task_dist_upload',
           'task_dist_pyhat_util',
           'task_dist_pyhat_peg']

dist_dir = Path('dist')
dist_py_dir = dist_dir / 'pip'
dist_js_dir = dist_dir / 'npm'


def task_dist():
    """Dist - create all distribution packages"""
    return {'actions': None,
            'task_dep': ['dist_pyhat_util',
                         'dist_pyhat_peg']}


def task_dist_upload():
    """Dist - upload to nibbler"""
    def upload():
        pass

    return {'actions': [upload],
            'task_dep': ['dist']}


def task_dist_pyhat_util():
    """Dist - create pyhat hat-util distribution"""
    return _get_task_dist_pyhat('hat-util', 'pyhat_util')


def task_dist_pyhat_peg():
    """Dist - create pyhat hat-peg distribution"""
    return _get_task_dist_pyhat('hat-peg', 'pyhat_peg')


def _get_task_dist_pyhat(name, build_task):
    src_path = pyhat_dir / name
    dst_path = dist_py_dir / name
    return {'actions': [(common.mkdir_p, [dst_path]),
                        (_create_wheel, [src_path, dst_path])],
            'task_dep': [build_task]}


def _create_wheel(src_path, dst_path):
    subprocess.run(['python', 'setup.py', '-q', 'bdist_wheel',
                    '--dist-dir', str(dst_path.resolve())],
                   cwd=str(src_path),
                   check=True)
