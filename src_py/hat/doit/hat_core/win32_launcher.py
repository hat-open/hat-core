from pathlib import Path
import subprocess

from hat.doit import c


__all__ = ['task_win32_launcher']


src_path = Path('src_c/hat/win32_launcher.c')
dst_dir = Path('build/win32_launcher')


def task_win32_launcher():
    "Win32 launcher - build"

    def build(name, module):
        if not name or not module:
            raise Exception('undefined arguments')
        dst_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run([c.cc, '-O2',
                        '-o', f'{dst_dir / name}.exe',
                        f'-DHAT_WIN32_LAUNCHER_PYTHON_MODULE="\\"{module}\\""',
                        str(src_path)],
                       check=True)

    return {'actions': [build],
            'params': [{'name': 'module',
                        'long': 'module',
                        'type': str,
                        'default': None,
                        'help': 'python module'},
                       {'name': 'name',
                        'long': 'name',
                        'type': str,
                        'default': None,
                        'help': 'launcher name'}]}
