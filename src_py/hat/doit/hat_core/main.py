from pathlib import Path
import itertools

from hat.doit import common

from hat.doit.hat_core.cache.tools import *  # NOQA
from hat.doit.hat_core.cache.vm.archlinux import *  # NOQA
from hat.doit.hat_core.cache.vm.key import *  # NOQA
from hat.doit.hat_core.cache.vm.win10 import *  # NOQA
from hat.doit.hat_core.check import *  # NOQA
from hat.doit.hat_core.dist import *  # NOQA
from hat.doit.hat_core.docs import *  # NOQA
from hat.doit.hat_core.duktape import *  # NOQA
from hat.doit.hat_core.format import *  # NOQA
from hat.doit.hat_core.homepage import *  # NOQA
from hat.doit.hat_core.jshat.app import *  # NOQA
from hat.doit.hat_core.jshat.deps import *  # NOQA
from hat.doit.hat_core.jshat.lib import *  # NOQA
from hat.doit.hat_core.jshat.view import *  # NOQA
from hat.doit.hat_core.pyhat import *  # NOQA
from hat.doit.hat_core.pymod import *  # NOQA
from hat.doit.hat_core.schemas import *  # NOQA
from hat.doit.hat_core.test import *  # NOQA
from hat.doit.hat_core.vm import *  # NOQA
from hat.doit.hat_core.win32_launcher import *  # NOQA
import hat.doit.hat_core.cache.tools
import hat.doit.hat_core.cache.vm.archlinux
import hat.doit.hat_core.cache.vm.key
import hat.doit.hat_core.cache.vm.win10
import hat.doit.hat_core.check
import hat.doit.hat_core.dist
import hat.doit.hat_core.docs
import hat.doit.hat_core.duktape
import hat.doit.hat_core.format
import hat.doit.hat_core.homepage
import hat.doit.hat_core.jshat.app
import hat.doit.hat_core.jshat.deps
import hat.doit.hat_core.jshat.lib
import hat.doit.hat_core.jshat.view
import hat.doit.hat_core.pyhat
import hat.doit.hat_core.pymod
import hat.doit.hat_core.schemas
import hat.doit.hat_core.test
import hat.doit.hat_core.vm
import hat.doit.hat_core.win32_launcher


__all__ = (['task_clean_all'] +
           hat.doit.hat_core.cache.tools.__all__ +
           hat.doit.hat_core.cache.vm.archlinux.__all__ +
           hat.doit.hat_core.cache.vm.key.__all__ +
           hat.doit.hat_core.cache.vm.win10.__all__ +
           hat.doit.hat_core.check.__all__ +
           hat.doit.hat_core.dist.__all__ +
           hat.doit.hat_core.docs.__all__ +
           hat.doit.hat_core.duktape.__all__ +
           hat.doit.hat_core.format.__all__ +
           hat.doit.hat_core.homepage.__all__ +
           hat.doit.hat_core.jshat.app.__all__ +
           hat.doit.hat_core.jshat.deps.__all__ +
           hat.doit.hat_core.jshat.lib.__all__ +
           hat.doit.hat_core.jshat.view.__all__ +
           hat.doit.hat_core.pyhat.__all__ +
           hat.doit.hat_core.pymod.__all__ +
           hat.doit.hat_core.schemas.__all__ +
           hat.doit.hat_core.test.__all__ +
           hat.doit.hat_core.vm.__all__ +
           hat.doit.hat_core.win32_launcher.__all__)


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
