from pathlib import Path
import subprocess
import sys


__all__ = ['task_check',
           'task_check_pyhat',
           'task_check_jshat',
           'task_check_sass']


eslint_path = Path('node_modules/.bin/eslint')
saslint_path = Path('node_modules/.bin/sass-lint')


def task_check():
    """Check - check all"""
    return {'actions': None,
            'task_dep': ['check_pyhat',
                         'check_jshat',
                         'check_sass']}


def task_check_pyhat():
    """Check - check pyhat with flake8"""
    return {'actions': [(_run_flake8, ['src_py']),
                        (_run_flake8, ['test_pytest'])]}


def task_check_jshat():
    """Check - check jshat with eslint"""
    return {'actions': [f'{eslint_path} src_js'],
            'task_dep': ['jshat_deps']}


def task_check_sass():
    """Check - check sass with sass-lint"""
    return {'actions': [f'{saslint_path} src_scss/**/*.scss'],
            'task_dep': ['jshat_deps']}


def _run_flake8(path):
    subprocess.run([sys.executable, '-m', 'flake8', '.'],
                   cwd=str(path),
                   check=True)
