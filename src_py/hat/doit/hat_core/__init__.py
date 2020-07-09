from pathlib import Path
import itertools

from hat.doit import common

from hat.doit.hat_core.articles import *  # NOQA
from hat.doit.hat_core.cache import *  # NOQA
from hat.doit.hat_core.check import *  # NOQA
from hat.doit.hat_core.dist import *  # NOQA
from hat.doit.hat_core.docs import *  # NOQA
from hat.doit.hat_core.duktape import *  # NOQA
from hat.doit.hat_core.format import *  # NOQA
from hat.doit.hat_core.homepage import *  # NOQA
from hat.doit.hat_core.jshat import *  # NOQA
from hat.doit.hat_core.pyhat import *  # NOQA
from hat.doit.hat_core.pymod import *  # NOQA
from hat.doit.hat_core.schemas import *  # NOQA
from hat.doit.hat_core.test import *  # NOQA
from hat.doit.hat_core.vm import *  # NOQA
from hat.doit.hat_core.win32_launcher import *  # NOQA
from hat.doit.hat_core import articles
from hat.doit.hat_core import cache
from hat.doit.hat_core import check
from hat.doit.hat_core import dist
from hat.doit.hat_core import docs
from hat.doit.hat_core import duktape
from hat.doit.hat_core import format
from hat.doit.hat_core import homepage
from hat.doit.hat_core import jshat
from hat.doit.hat_core import pyhat
from hat.doit.hat_core import pymod
from hat.doit.hat_core import schemas
from hat.doit.hat_core import test
from hat.doit.hat_core import vm
from hat.doit.hat_core import win32_launcher


__all__ = (['task_clean_all'] +
           articles.__all__ +
           cache.__all__ +
           check.__all__ +
           dist.__all__ +
           docs.__all__ +
           duktape.__all__ +
           format.__all__ +
           homepage.__all__ +
           jshat.__all__ +
           pyhat.__all__ +
           pymod.__all__ +
           schemas.__all__ +
           test.__all__ +
           vm.__all__ +
           win32_launcher.__all__)


build_dir = Path('build')
dist_dir = Path('dist')
src_py_dir = Path('src_py')
src_c_dir = Path('src_c')


def task_clean_all():
    """Clean all"""

    def clean():
        src_py_patterns = ['*.so',
                           '*.pyd',
                           '*.dylib',
                           '*.dll',
                           'json_schema_repo.json',
                           'sbs_repo.json',
                           'asn1_repo.json']
        targets = [build_dir, dist_dir,
                   *itertools.chain.from_iterable(src_py_dir.rglob(i)
                                                  for i in src_py_patterns),
                   *(src_c_dir / 'hat').glob('sbs_defs.*')]
        common.rm_rf(*targets)

    return {'actions': [clean]}
