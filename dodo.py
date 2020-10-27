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
src_py_path = str(Path('src_py').resolve())

sys.path += [src_py_path]
if pythonpath:
    os.environ['PYTHONPATH'] = f'{src_py_path}{os.pathsep}{pythonpath}'
else:
    os.environ['PYTHONPATH'] = src_py_path


from hat.doit.hat_core import *  # NOQA
