import subprocess


__all__ = ['task_check',
           'task_check_pyhat']


def task_check():
    """Check - check all"""
    return {'actions': None,
            'task_dep': ['check_pyhat']}


def task_check_pyhat():
    """Check - check pyhat with flake8"""
    def check():
        subprocess.run(['python', '-m', 'flake8', '.'],
                       cwd='src_py',
                       check=True)
        subprocess.run(['python', '-m', 'flake8', '.'],
                       cwd='test_pytest',
                       check=True)

    return {'actions': [check]}
