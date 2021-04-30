from pathlib import Path
import subprocess
import sys

from hat.doit import common


__all__ = ['task_win32_launcher']


src_path = Path('src_c/hat/win32_launcher.c')
dst_dir = Path('build/win32_launcher')

if sys.platform == 'win32':
    cc = common.cc
    windres = 'windres'
else:
    cc = 'x86_64-w64-mingw32-gcc'
    windres = 'x86_64-w64-mingw32-windres'


def task_win32_launcher():
    "Win32 launcher - build"

    def build(name, cmd, icon, admin):
        if not name or not cmd:
            raise Exception('undefined arguments')
        cmd = cmd.replace('\\', '\\\\')
        dst_dir.mkdir(parents=True, exist_ok=True)
        sources = [str(src_path)]

        if icon or admin:
            rc_path = dst_dir / f'{name}.rc'
            rc_o_path = rc_path.with_suffix('.o')
            sources.append(rc_o_path)

            with open(rc_path, 'w', encoding='utf-8') as rc:
                rc.write('#include "winuser.h"\n')

                if icon:
                    icon = str(Path(icon).resolve()).replace('\\', '\\\\')
                    rc.write(f'iconId ICON "{icon}"\n')

                if admin:
                    manifest_path = dst_dir / f'{name}.exe.manifest'
                    with open(manifest_path, 'w', encoding='utf-8') as man:
                        man.write(_admin_manifest)
                    manifest = str(Path(manifest_path).resolve()).replace(
                        '\\', '\\\\')
                    rc.write(f'1 RT_MANIFEST "{manifest}"\n')

            subprocess.run([windres, str(rc_path), str(rc_o_path)],
                           check=True)

        subprocess.run([cc, '-O2', '-mwindows',
                        '-o', f'{dst_dir / name}.exe',
                        f'-DHAT_WIN32_LAUNCHER_CMD="\\"{cmd}\\""',
                        *sources],
                       check=True)

    return {'actions': [build],
            'params': [{'name': 'cmd',
                        'long': 'cmd',
                        'type': str,
                        'default': None,
                        'help': 'relative command'},
                       {'name': 'name',
                        'long': 'name',
                        'type': str,
                        'default': None,
                        'help': 'launcher name'},
                       {'name': 'icon',
                        'long': 'icon',
                        'type': str,
                        'default': None,
                        'help': 'optional icon path'},
                       {'name': 'admin',
                        'long': 'admin',
                        'type': bool,
                        'default': False,
                        'help': 'administrator privileges'}]}


_admin_manifest = r"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1"
          manifestVersion="1.0">
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v2">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel
          level="requireAdministrator"
          uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
</assembly>
"""
