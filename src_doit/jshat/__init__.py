import subprocess

from hat.doit import common

from .app import *  # NOQA
from .lib import *  # NOQA
from .view import *  # NOQA
from . import app
from . import lib
from . import view


__all__ = ['task_jshat_deps',
           'task_jshat_deps_clean',
           *app.__all__,
           *lib.__all__,
           *view.__all__]


def task_jshat_deps():
    """JsHat dependencies - install"""
    def patch():
        subprocess.run(['patch', '-r', '/dev/null', '--forward', '-p0',
                        '-i', 'node_modules.patch'],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

    return {'actions': ['yarn install --silent',
                        patch]}


def task_jshat_deps_clean():
    """JsHat dependencies - remove"""
    return {'actions': [(common.rm_rf, ['node_modules', 'yarn.lock'])]}
