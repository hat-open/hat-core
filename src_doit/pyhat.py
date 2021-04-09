from pathlib import Path
import platform
import shutil
import sys

from hat.doit import common

from .duktape import lib_path as duktape_lib_path
from .pymod import sbs_mod_path
from .pymod import sqlite3_mod_path


__all__ = ['task_pyhat_util',
           'task_pyhat_aio',
           'task_pyhat_json',
           'task_pyhat_qt',
           'task_pyhat_peg',
           'task_pyhat_stc',
           'task_pyhat_sbs',
           'task_pyhat_chatter',
           'task_pyhat_juggler',
           'task_pyhat_duktape',
           'task_pyhat_sqlite3',
           'task_pyhat_asn1',
           'task_pyhat_drivers',
           'task_pyhat_syslog',
           'task_pyhat_orchestrator',
           'task_pyhat_monitor',
           'task_pyhat_event',
           'task_pyhat_gateway',
           'task_pyhat_gui',
           'task_pyhat_manager']


build_dir = Path('build/pyhat')
src_json_dir = Path('schemas_json')
src_sbs_dir = Path('schemas_sbs')
src_py_dir = Path('src_py')

python_tag = 'cp38.cp39'


def task_pyhat_clean():
    """PyHat - clean"""
    return {'actions': [(common.rm_rf, [build_dir])]}


def task_pyhat_util():
    """PyHat - build hat-util"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-util')
        yield src_py_dir / 'hat/util.py', dst_dir / 'hat/util.py'

    return _get_task_build(name='hat-util',
                           description='Hat utility library',
                           readme_path=Path('README.hat-util.rst'),
                           dependencies=[],
                           mappings=mappings)


def task_pyhat_aio():
    """PyHat - build hat-aio"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-aio')
        yield src_py_dir / 'hat/aio.py', dst_dir / 'hat/aio.py'

    return _get_task_build(name='hat-aio',
                           description='Hat async utility library',
                           readme_path=Path('README.hat-aio.rst'),
                           dependencies=[],
                           mappings=mappings)


def task_pyhat_json():
    """PyHat - build hat-json"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-json')
        json_schema_repo = src_py_dir / 'hat/json/json_schema_repo.json'
        for i in (src_py_dir / 'hat/json').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield json_schema_repo, (dst_dir /
                                 json_schema_repo.relative_to(src_py_dir))

    return _get_task_build(name='hat-json',
                           description='Hat JSON library',
                           readme_path=Path('README.hat-json.rst'),
                           dependencies=['pyyaml',
                                         'jsonschema',
                                         'jsonpatch'],
                           mappings=mappings)


def task_pyhat_qt():
    """PyHat - build hat-qt"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-qt')
        yield src_py_dir / 'hat/qt.py', dst_dir / 'hat/qt.py'

    return _get_task_build(name='hat-qt',
                           description='Hat Qt utility library',
                           readme_path=Path('README.hat-qt.rst'),
                           dependencies=['PySide2',
                                         'hat-aio'],
                           mappings=mappings)


def task_pyhat_peg():
    """PyHat - build hat-peg"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-peg')
        src_py = src_py_dir / 'hat/peg.py'
        yield src_py, dst_dir / src_py.relative_to(src_py_dir)

    return _get_task_build(name='hat-peg',
                           description='Hat PEG parser',
                           readme_path=Path('README.hat-peg.rst'),
                           dependencies=['hat-util'],
                           mappings=mappings)


def task_pyhat_stc():
    """PyHat - build hat-stc"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-stc')
        src_py = src_py_dir / 'hat/stc.py'
        yield src_py, dst_dir / src_py.relative_to(src_py_dir)

    return _get_task_build(name='hat-stc',
                           description='Hat statechart engine',
                           readme_path=Path('README.hat-stc.rst'),
                           dependencies=['hat-aio'],
                           mappings=mappings)


def task_pyhat_sbs():
    """PyHat - build hat-sbs"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-sbs')
        for i in (src_py_dir / 'hat/sbs').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield sbs_mod_path, (dst_dir /
                             sbs_mod_path.relative_to(src_py_dir))

    return _get_task_build(name='hat-sbs',
                           description='Hat simple binary serializer',
                           readme_path=Path('README.hat-sbs.rst'),
                           dependencies=['hat-json',
                                         'hat-peg'],
                           mappings=mappings,
                           platform_specific=True)


def task_pyhat_chatter():
    """PyHat - build hat-chatter"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-chatter')
        sbs_repo = src_py_dir / 'hat/chatter/sbs_repo.json'
        for i in (src_py_dir / 'hat/chatter').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield sbs_repo, dst_dir / sbs_repo.relative_to(src_py_dir)

    return _get_task_build(name='hat-chatter',
                           description='Hat Chatter protocol',
                           readme_path=Path('README.hat-chatter.rst'),
                           dependencies=['hat-util',
                                         'hat-sbs'],
                           mappings=mappings)


def task_pyhat_juggler():
    """PyHat - build hat-juggler"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-juggler')
        src_py = src_py_dir / 'hat/juggler.py'
        yield src_py, dst_dir / src_py.relative_to(src_py_dir)

    return _get_task_build(name='hat-juggler',
                           description='Hat Juggler protocol',
                           readme_path=Path('README.hat-juggler.rst'),
                           dependencies=['aiohttp',
                                         'hat-util'],
                           mappings=mappings)


def task_pyhat_duktape():
    """PyHat - build hat-duktape"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-duktape')
        for i in (src_py_dir / 'hat/duktape').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield duktape_lib_path, (dst_dir /
                                 duktape_lib_path.relative_to(src_py_dir))

    return _get_task_build(name='hat-duktape',
                           description='Hat Python Duktape JS wrapper',
                           readme_path=Path('README.hat-duktape.rst'),
                           dependencies=[],
                           mappings=mappings,
                           platform_specific=True)


def task_pyhat_sqlite3():
    """PyHat - build hat-sqlite3"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-sqlite3')
        for i in (src_py_dir / 'hat/sqlite3').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield sqlite3_mod_path, (dst_dir /
                                 sqlite3_mod_path.relative_to(src_py_dir))

    return _get_task_build(name='hat-sqlite3',
                           description='Hat Sqlite3 build',
                           readme_path=Path('README.hat-sqlite3.rst'),
                           dependencies=[],
                           mappings=mappings,
                           platform_specific=True)


def task_pyhat_asn1():
    """PyHat - build hat-asn1"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-asn1')
        for i in (src_py_dir / 'hat/asn1').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)

    return _get_task_build(name='hat-asn1',
                           description='Hat ASN.1 parser and encoder',
                           readme_path=Path('README.hat-asn1.rst'),
                           dependencies=['hat-util',
                                         'hat-json',
                                         'hat-peg'],
                           mappings=mappings)


def task_pyhat_drivers():
    """PyHat - build hat-drivers"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-drivers')
        asn1_repos = [src_py_dir / 'hat/drivers/copp/asn1_repo.json',
                      src_py_dir / 'hat/drivers/acse/asn1_repo.json',
                      src_py_dir / 'hat/drivers/mms/asn1_repo.json']
        for i in (src_py_dir / 'hat/drivers').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        for asn1_repo in asn1_repos:
            yield asn1_repo, dst_dir / asn1_repo.relative_to(src_py_dir)

    return _get_task_build(name='hat-drivers',
                           description='Hat communication drivers',
                           readme_path=Path('README.hat-drivers.rst'),
                           dependencies=['pyserial',
                                         'hat-util',
                                         'hat-aio',
                                         'hat-json',
                                         'hat-asn1'],
                           mappings=mappings)


def task_pyhat_syslog():
    """PyHat - build hat-syslog"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-syslog')
        json_schema_repo = (src_py_dir /
                            'hat/syslog/json_schema_repo.json')
        jshat_build = Path('build/jshat/app/syslog')
        for i in (src_py_dir / 'hat/syslog').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield json_schema_repo, (dst_dir /
                                 json_schema_repo.relative_to(src_py_dir))
        for i in jshat_build.rglob('*'):
            if i.is_dir():
                continue
            yield i, (dst_dir / 'hat/syslog/server/ui'
                              / i.relative_to(jshat_build))

    return _get_task_build(
        name='hat-syslog',
        description='Hat Syslog',
        readme_path=Path('README.hat-syslog.rst'),
        dependencies=['appdirs',
                      'click',
                      'hat-util',
                      'hat-aio',
                      'hat-json',
                      'hat-juggler',
                      'hat-sqlite3'],
        mappings=mappings,
        console_scripts=['hat-syslog = hat.syslog.server.main:main'],
        task_dep=['jshat_app_syslog'])


def task_pyhat_orchestrator():
    """PyHat - build hat-orchestrator"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-orchestrator')
        json_schema_repo = (src_py_dir /
                            'hat/orchestrator/json_schema_repo.json')
        jshat_build = Path('build/jshat/app/orchestrator')
        for i in (src_py_dir / 'hat/orchestrator').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield json_schema_repo, (dst_dir /
                                 json_schema_repo.relative_to(src_py_dir))
        for i in jshat_build.rglob('*'):
            if i.is_dir():
                continue
            yield i, (dst_dir / 'hat/orchestrator/ui'
                              / i.relative_to(jshat_build))

    return _get_task_build(
        name='hat-orchestrator',
        description='Hat Orchestrator',
        readme_path=Path('README.hat-orchestrator.rst'),
        dependencies=['appdirs',
                      'click',
                      'hat-util',
                      'hat-aio',
                      'hat-json',
                      'hat-juggler'],
        mappings=mappings,
        console_scripts=['hat-orchestrator = hat.orchestartor.main:main'],
        task_dep=['jshat_app_orchestrator'])


def task_pyhat_monitor():
    """PyHat - build hat-monitor"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-monitor')
        json_schema_repo = src_py_dir / 'hat/monitor/json_schema_repo.json'
        sbs_repo = src_py_dir / 'hat/monitor/sbs_repo.json'
        jshat_build = Path('build/jshat/app/monitor')
        for i in (src_py_dir / 'hat/monitor').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield json_schema_repo, (dst_dir /
                                 json_schema_repo.relative_to(src_py_dir))
        yield sbs_repo, dst_dir / sbs_repo.relative_to(src_py_dir)
        for i in jshat_build.rglob('*'):
            if i.is_dir():
                continue
            yield i, (dst_dir / 'hat/monitor/server/ui'
                              / i.relative_to(jshat_build))

    return _get_task_build(
        name='hat-monitor',
        description='Hat Monitor Server and client',
        readme_path=Path('README.hat-monitor.rst'),
        dependencies=['appdirs',
                      'click',
                      'hat-util',
                      'hat-json',
                      'hat-aio',
                      'hat-sbs',
                      'hat-chatter',
                      'hat-juggler'],
        mappings=mappings,
        console_scripts=['hat-monitor = hat.monitor.server.main:main'],
        task_dep=['jshat_app_monitor'])


def task_pyhat_event():
    """PyHat - build hat-event"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-event')
        json_schema_repo = src_py_dir / 'hat/event/json_schema_repo.json'
        sbs_repo = src_py_dir / 'hat/event/sbs_repo.json'
        for i in (src_py_dir / 'hat/event').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield json_schema_repo, (dst_dir /
                                 json_schema_repo.relative_to(src_py_dir))
        yield sbs_repo, dst_dir / sbs_repo.relative_to(src_py_dir)

    return _get_task_build(
        name='hat-event',
        description='Hat Event Server and client',
        readme_path=Path('README.hat-event.rst'),
        dependencies=['appdirs',
                      'click',
                      'lmdb',
                      'hat-util',
                      'hat-aio',
                      'hat-json',
                      'hat-sbs',
                      'hat-chatter',
                      'hat-sqlite3',
                      'hat-monitor'],
        mappings=mappings,
        console_scripts=['hat-event = hat.event.server.main:main'])


def task_pyhat_gateway():
    """PyHat - build hat-gateway"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-gateway')
        json_schema_repo = src_py_dir / 'hat/gateway/json_schema_repo.json'
        for i in (src_py_dir / 'hat/gateway').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield json_schema_repo, (dst_dir /
                                 json_schema_repo.relative_to(src_py_dir))

    return _get_task_build(
        name='hat-gateway',
        description='Hat remote communication device gateway',
        readme_path=Path('README.hat-gateway.rst'),
        dependencies=['appdirs',
                      'click',
                      'hat-util',
                      'hat-aio',
                      'hat-json',
                      'hat-sbs',
                      'hat-chatter',
                      'hat-monitor',
                      'hat-event'],
        mappings=mappings,
        console_scripts=['hat-gateway = hat.gateway.main:main'])


def task_pyhat_gui():
    """PyHat - build hat-gui"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-gui')
        json_schema_repo = src_py_dir / 'hat/gui/json_schema_repo.json'
        jshat_app_build = Path('build/jshat/app/gui')
        jshat_view_build = Path('build/jshat/view')
        for i in (src_py_dir / 'hat/gui').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        yield json_schema_repo, (dst_dir /
                                 json_schema_repo.relative_to(src_py_dir))
        for i in jshat_app_build.rglob('*'):
            if i.is_dir():
                continue
            yield i, (dst_dir / 'hat/gui/ui'
                              / i.relative_to(jshat_app_build))
        for i in jshat_view_build.rglob('*'):
            if i.is_dir():
                continue
            yield i, (dst_dir / 'hat/gui/views'
                              / i.relative_to(jshat_view_build))

    return _get_task_build(
        name='hat-gui',
        description='Hat GUI server',
        readme_path=Path('README.hat-gui.rst'),
        dependencies=['appdirs',
                      'click',
                      'hat-util',
                      'hat-aio',
                      'hat-json',
                      'hat-sbs',
                      'hat-chatter',
                      'hat-monitor',
                      'hat-event',
                      'hat-juggler'],
        mappings=mappings,
        console_scripts=['hat-gui = hat.gui.main:main'],
        task_dep=['jshat_app_gui',
                  'jshat_view'])


def task_pyhat_manager():
    """PyHat - build hat-manager"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-manager')
        for i in (src_py_dir / 'hat/manager').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)

        json_schema_repo = src_py_dir / 'hat/manager/json_schema_repo.json'
        yield json_schema_repo, (dst_dir /
                                 json_schema_repo.relative_to(src_py_dir))

        jshat_dirs = [(Path('build/jshat/app/manager'),
                       dst_dir / 'hat/manager/ui')]
        for jshat_src_dir, jshat_dst_dir in jshat_dirs:
            for i in jshat_src_dir.rglob('*'):
                if i.is_dir():
                    continue
                yield i, (jshat_dst_dir / i.relative_to(jshat_src_dir))

    return _get_task_build(
        name='hat-manager',
        description='Hat managment GUI',
        readme_path=Path('README.hat-manager.rst'),
        dependencies=['appdirs',
                      'click',
                      'hat-aio',
                      'hat-drivers',
                      'hat-event',
                      'hat-json',
                      'hat-juggler',
                      'hat-qt',
                      'hat-util'],
        mappings=mappings,
        console_scripts=['hat-manager = hat.manager.main:main'],
        task_dep=['jshat_app_manager'])


def _get_task_build(name, description, readme_path, dependencies, mappings, *,
                    optional_dependencies={}, console_scripts=[],
                    gui_scripts=[], platform_specific=False, task_dep=[]):
    dst_dir = _get_build_dst_dir(name)
    setup_path = dst_dir / 'setup.py'
    manifest_path = dst_dir / 'MANIFEST.in'
    src_paths = list(src_path for src_path, _ in mappings())
    dst_paths = [setup_path] + list(dst_path for _, dst_path in mappings())
    return {'actions': [(common.mkdir_p, [dst_dir]),
                        (_copy_files, [mappings]),
                        (_create_manifest, [manifest_path, mappings]),
                        (_create_setup_py, [setup_path, name, description,
                                            readme_path, dependencies,
                                            optional_dependencies,
                                            console_scripts, gui_scripts,
                                            platform_specific])],
            'file_dep': src_paths,
            'targets': dst_paths,
            'task_dep': [*task_dep]}


def _get_build_dst_dir(name):
    return build_dir / name


def _copy_files(mappings):
    for src_path, dst_path in mappings():
        if not dst_path.parent.exists():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(src_path), str(dst_path))


def _create_setup_py(path, name, description, readme_path, dependencies,
                     optional_dependencies, console_scripts, gui_scripts,
                     platform_specific):
    plat_name = _get_plat_name() if platform_specific else 'any'
    version = common.get_version(common.VersionType.PIP)
    readme = _get_readme(readme_path)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"from setuptools import setup\n\n\n"
                f"readme = {repr(readme)}  # NOQA\n\n"
                f"setup(name={repr(name)},\n"
                f"      version={repr(version)},\n"
                f"      description={repr(description)},\n"
                f"      long_description=readme,\n"
                f"      long_description_content_type='text/x-rst',\n"
                f"      url='https://github.com/hat-open/hat-core',\n"
                f"      packages=['hat'],\n"
                f"      include_package_data=True,\n"
                f"      install_requires={repr(dependencies)},\n"
                f"      extras_require={repr(optional_dependencies)},\n"
                f"      python_requires='>=3.8',\n"
                f"      license='Apache-2.0',\n"
                f"      zip_safe=False,\n"
                f"      classifiers=[\n"
                f"          'Programming Language :: Python :: 3',\n"
                f"          'License :: OSI Approved :: Apache Software License',\n"  # NOQA
                f"      ],\n"
                f"      options={{\n"
                f"          'bdist_wheel': {{\n"
                f"              'python_tag': {repr(python_tag)},\n"
                f"              'py_limited_api': {repr(python_tag)},\n"
                f"              'plat_name': '{plat_name}'\n"
                f"          }}\n"
                f"      }},\n"
                f"      entry_points={{\n"
                f"          'console_scripts': {repr(console_scripts)},\n"
                f"          'gui_scripts': {repr(gui_scripts)}\n"
                f"      }})\n")


def _create_manifest(path, mappings):
    with open(path, 'w', encoding='utf-8') as f:
        for _, i in mappings():
            f.write(f"include {i.relative_to(path.parent)}\n")


def _get_plat_name():
    arch, _ = platform.architecture()
    if sys.platform == 'win32' and arch == '32bit':
        return 'win32'
    if sys.platform == 'win32' and arch == '64bit':
        return 'win_amd64'
    if sys.platform == 'linux' and arch == '64bit':
        return 'manylinux1_x86_64'
    if sys.platform == 'darwin' and arch == '64bit':
        return 'macosx_10_13_x86_64'
    raise NotImplementedError()


def _get_readme(readme_path):
    with open(readme_path, encoding='utf-8') as f:
        return f.read().strip()
