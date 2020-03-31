from pathlib import Path

from hat.doit import common

from hat.doit.hat_core.check import *  # NOQA
from hat.doit.hat_core.dist import *  # NOQA
from hat.doit.hat_core.docs import *  # NOQA
from hat.doit.hat_core.homepage import *  # NOQA
from hat.doit.hat_core.pyhat import *  # NOQA
from hat.doit.hat_core.test import *  # NOQA
import hat.doit.hat_core.check
import hat.doit.hat_core.dist
import hat.doit.hat_core.docs
import hat.doit.hat_core.homepage
import hat.doit.hat_core.pyhat
import hat.doit.hat_core.test


__all__ = (['task_clean_all'] +
           hat.doit.hat_core.check.__all__ +
           hat.doit.hat_core.dist.__all__ +
           hat.doit.hat_core.docs.__all__ +
           hat.doit.hat_core.homepage.__all__ +
           hat.doit.hat_core.pyhat.__all__ +
           hat.doit.hat_core.test.__all__)


build_dir = Path('build')
dist_dir = Path('dist')


def task_clean_all():
    """Clean all"""
    return {'actions': [(common.rm_rf, [build_dir,
                                        dist_dir])]}
