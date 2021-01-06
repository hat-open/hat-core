from pathlib import Path
import itertools

from hat.doit import common

from .articles import *  # NOQA
from .cache import *  # NOQA
from .check import *  # NOQA
from .dist import *  # NOQA
from .docs import *  # NOQA
from .duktape import *  # NOQA
from .format import *  # NOQA
from .homepage import *  # NOQA
from .jshat import *  # NOQA
from .pyhat import *  # NOQA
from .pymod import *  # NOQA
from .schemas import *  # NOQA
from .test import *  # NOQA
from .vm import *  # NOQA
from .win32_launcher import *  # NOQA
from . import articles
from . import cache
from . import check
from . import dist
from . import docs
from . import duktape
from . import format
from . import homepage
from . import jshat
from . import pyhat
from . import pymod
from . import schemas
from . import test
from . import vm
from . import win32_launcher


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
src_js_dir = Path('src_js')
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
        targets = [build_dir,
                   dist_dir,
                   src_js_dir / '@hat-core/hue-manager/assets.js',
                   *itertools.chain.from_iterable(src_py_dir.rglob(i)
                                                  for i in src_py_patterns),
                   *(src_c_dir / 'hat').glob('sbs_defs.*')]
        common.rm_rf(*targets)

    return {'actions': [clean]}
