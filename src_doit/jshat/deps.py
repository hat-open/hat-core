import subprocess

from hat.doit import common


__all__ = ['task_jshat_deps',
           'task_jshat_deps_clean']


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
