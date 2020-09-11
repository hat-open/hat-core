from pathlib import Path
import subprocess
import sys

from hat.doit import c


__all__ = ['task_win32_launcher']


src_path = Path('src_c/hat/win32_launcher.c')
dst_dir = Path('build/win32_launcher')

if sys.platform == 'win32':
    cc = c.cc
    windres = 'windres'
else:
    cc = 'i686-w64-mingw32-gcc'
    windres = 'i686-w64-mingw32-windres'


def task_win32_launcher():
    "Win32 launcher - build"

    def build(name, module, icon):
        if not name or not module:
            raise Exception('undefined arguments')
        dst_dir.mkdir(parents=True, exist_ok=True)
        sources = [str(src_path)]

        if icon:
            icon = str(Path(icon).resolve()).replace('\\', '\\\\')
            rc_path = dst_dir / 'res.rc'
            rc_o_path = rc_path.with_suffix('.o')
            sources.append(rc_o_path)
            with open(rc_path, 'w', encoding='utf-8') as f:
                f.write(f'#include "winuser.h"\n'
                        f'iconId ICON "{icon}"\n')
            subprocess.run([windres, str(rc_path), str(rc_o_path)],
                           check=True)

        subprocess.run([cc, '-O2', '-mwindows',
                        '-o', f'{dst_dir / name}.exe',
                        f'-DHAT_WIN32_LAUNCHER_PYTHON_MODULE="\\"{module}\\""',
                        *sources],
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
                        'help': 'launcher name'},
                       {'name': 'icon',
                        'long': 'icon',
                        'type': str,
                        'default': None,
                        'help': 'optional icon path'}]}
