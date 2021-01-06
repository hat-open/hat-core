import multiprocessing
import os
import sys
from pathlib import Path

num_process = os.environ.get('DOIT_NUM_PROCESS')
if num_process:
    num_process = int(num_process)
elif sys.platform == 'darwin':
    num_process = 0
else:
    num_process = multiprocessing.cpu_count()

DOIT_CONFIG = {'backend': 'sqlite3',
               'default_tasks': ['dist'],
               'verbosity': 2,
               'num_process': num_process}

pythonpath = os.environ.get('PYTHONPATH')
package_path = Path(__file__).parent.resolve()
src_py_path = package_path / 'src_py'

sys.path = [str(src_py_path), *sys.path]
if pythonpath:
    os.environ['PYTHONPATH'] = f'{src_py_path}{os.pathsep}{pythonpath}'
else:
    os.environ['PYTHONPATH'] = str(src_py_path)


from src_doit import *  # NOQA
