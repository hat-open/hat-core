from pathlib import Path

from hat.doit import common

from hat.doit.hat_core.cache.tools import *  # NOQA
from hat.doit.hat_core.cache.vm.archlinux import *  # NOQA
from hat.doit.hat_core.cache.vm.key import *  # NOQA
from hat.doit.hat_core.cache.vm.win10 import *  # NOQA
from hat.doit.hat_core.check import *  # NOQA
from hat.doit.hat_core.dist import *  # NOQA
from hat.doit.hat_core.docs import *  # NOQA
from hat.doit.hat_core.duktape import *  # NOQA
from hat.doit.hat_core.homepage import *  # NOQA
from hat.doit.hat_core.jshat.deps import *  # NOQA
from hat.doit.hat_core.jshat.lib import *  # NOQA
from hat.doit.hat_core.pyhat import *  # NOQA
from hat.doit.hat_core.pymod import *  # NOQA
from hat.doit.hat_core.test import *  # NOQA
from hat.doit.hat_core.vm import *  # NOQA
import hat.doit.hat_core.cache.tools
import hat.doit.hat_core.cache.vm.archlinux
import hat.doit.hat_core.cache.vm.key
import hat.doit.hat_core.cache.vm.win10
import hat.doit.hat_core.check
import hat.doit.hat_core.dist
import hat.doit.hat_core.docs
import hat.doit.hat_core.duktape
import hat.doit.hat_core.homepage
import hat.doit.hat_core.jshat.deps
import hat.doit.hat_core.jshat.lib
import hat.doit.hat_core.pyhat
import hat.doit.hat_core.pymod
import hat.doit.hat_core.test
import hat.doit.hat_core.vm


__all__ = (['task_clean_all'] +
           hat.doit.hat_core.cache.tools.__all__ +
           hat.doit.hat_core.cache.vm.archlinux.__all__ +
           hat.doit.hat_core.cache.vm.key.__all__ +
           hat.doit.hat_core.cache.vm.win10.__all__ +
           hat.doit.hat_core.check.__all__ +
           hat.doit.hat_core.dist.__all__ +
           hat.doit.hat_core.docs.__all__ +
           hat.doit.hat_core.duktape.__all__ +
           hat.doit.hat_core.homepage.__all__ +
           hat.doit.hat_core.jshat.deps.__all__ +
           hat.doit.hat_core.jshat.lib.__all__ +
           hat.doit.hat_core.pyhat.__all__ +
           hat.doit.hat_core.pymod.__all__ +
           hat.doit.hat_core.test.__all__ +
           hat.doit.hat_core.vm.__all__)


build_dir = Path('build')
dist_dir = Path('dist')


def task_clean_all():
    """Clean all"""
    return {'actions': [(common.rm_rf, [build_dir,
                                        dist_dir])]}
