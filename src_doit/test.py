import subprocess
import sys


__all__ = ['task_test']


def task_test():
    """Test - run pytest tests"""
    def run(args):
        cmd = [sys.executable, '-m', 'pytest',
               '-s', '-p', 'no:cacheprovider',
               '-m', 'not tutorial']
        if args:
            cmd += args
        subprocess.run(cmd,
                       cwd='test_pytest',
                       check=True)

    return {'actions': [run],
            'pos_arg': 'args',
            'task_dep': ['duktape',
                         'pymod',
                         'schemas']}
