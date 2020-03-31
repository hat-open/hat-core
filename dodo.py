import sys
import os
from pathlib import Path


DOIT_CONFIG = {'backend': 'sqlite3',
               'verbosity': 2}

pythonpath = os.environ.get('PYTHONPATH')
src_py_path = str(Path('src_py').resolve())

sys.path += [src_py_path]
if pythonpath:
    pythonpath_del = ';' if sys.platform == 'win32' else ':'
    os.environ['PYTHONPATH'] = f'{src_py_path}{pythonpath_del}{pythonpath}'
else:
    os.environ['PYTHONPATH'] = src_py_path


from hat.doit.hat_core.main import *  # NOQA
