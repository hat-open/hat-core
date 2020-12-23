from pathlib import Path

from hat.doit import c


__all__ = ['task_duktape',
           'task_duktape_obj',
           'task_duktape_dep']


src_dir = Path('src_c')
build_dir = Path('build/duktape')
src_paths = list((src_dir / 'duktape').rglob('*.c'))
lib_path = Path(f'src_py/hat/duktape/duktape{c.lib_suffix}')

cc_flags = ['-fPIC', '-O2']


def task_duktape():
    """Duktape - build dynamic library"""
    return c.get_task_lib(lib_path, src_paths, src_dir, build_dir)


def task_duktape_obj():
    """Duktape - build .o files"""
    yield from c.get_task_objs(src_paths, src_dir, build_dir,
                               cc_flags=cc_flags)


def task_duktape_dep():
    """Duktape - build .d files"""
    yield from c.get_task_deps(src_paths, src_dir, build_dir)
