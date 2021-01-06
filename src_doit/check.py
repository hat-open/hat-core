import subprocess
import sys


__all__ = ['task_check',
           'task_check_pyhat',
           'task_check_jshat',
           'task_check_sass']


def task_check():
    """Check - check all"""
    return {'actions': None,
            'task_dep': ['check_pyhat',
                         'check_jshat',
                         'check_sass']}


def task_check_pyhat():
    """Check - check pyhat with flake8"""
    def check():
        subprocess.run([sys.executable, '-m', 'flake8', '.'],
                       cwd='src_py',
                       check=True)
        subprocess.run([sys.executable, '-m', 'flake8', '.'],
                       cwd='test_pytest',
                       check=True)

    return {'actions': [check]}


def task_check_jshat():
    """Check - check jshat with eslint"""
    return {'actions': ['yarn run --silent check_js'],
            'task_dep': ['jshat_deps']}


def task_check_sass():
    """Check - check sass with sass-lint"""
    return {'actions': ['yarn run --silent check_sass'],
            'task_dep': ['jshat_deps']}
