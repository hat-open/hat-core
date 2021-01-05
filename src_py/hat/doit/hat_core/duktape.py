from pathlib import Path

from hat.doit import common


__all__ = ['task_duktape',
           'task_duktape_obj',
           'task_duktape_dep']


lib_path = Path(f'src_py/hat/duktape/duktape{common.lib_suffix}')

build = common.CBuild(
    src_paths=list(Path('src_c/duktape').rglob('*.c')),
    src_dir=Path('src_c'),
    build_dir=Path('build/duktape'),
    cc_flags=['-fPIC', '-O2'])


def task_duktape():
    """Duktape - build dynamic library"""
    return build.get_task_lib(lib_path)


def task_duktape_obj():
    """Duktape - build .o files"""
    yield from build.get_task_objs()


def task_duktape_dep():
    """Duktape - build .d files"""
    yield from build.get_task_deps()
