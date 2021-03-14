from pathlib import Path

from hat.doit import common

from .docs import dst_dir as docs_src_dir


__all__ = ['task_homepage',
           'task_homepage_pages',
           'task_homepage_static',
           'task_homepage_sass',
           'task_homepage_docs']


src_dir = Path('homepage')
dst_dir = Path('build/homepage')
docs_dst_dir = dst_dir / 'docs'


def task_homepage():
    """Homepage - build"""
    return {'actions': None,
            'task_dep': ['homepage_pages',
                         'homepage_static',
                         'homepage_sass',
                         'homepage_docs']}


def task_homepage_pages():
    """Homepage - build pages"""
    for i in src_dir.rglob('*.html'):
        if i.stem.startswith('_'):
            continue
        name = i.relative_to(src_dir).with_suffix('').as_posix()
        src_path = src_dir / f"{name}.html"
        dst_path = dst_dir / f"{name}.html"
        yield {'name': str(dst_path),
               'actions': [(common.mako_build, [src_dir, src_path, dst_path,
                                                {}])],
               'targets': [dst_path]}


def task_homepage_static():
    """Homepage - copy static assets"""
    mappings = {Path('logo/favicon.ico'): dst_dir / 'favicon.ico'}

    for src_path, dst_path in mappings.items():
        yield {'name': str(dst_path),
               'actions': [(common.mkdir_p, [dst_path.parent]),
                           (common.cp_r, [src_path, dst_path])],
               'file_dep': [src_path],
               'targets': [dst_path]}


def task_homepage_sass():
    """Homepage - build sass"""
    mappings = {
        path: dst_dir / path.relative_to(src_dir).with_suffix('.css')
        for path in src_dir.rglob('*.scss')
        if not path.name.startswith('_')}

    for src_path, dst_path in mappings.items():
        yield {'name': str(dst_path),
               'actions': [(common.mkdir_p, [dst_path.parent]),
                           f'node_modules/.bin/sass --no-source-map'
                           f' {src_path} {dst_path}'],
               'targets': [dst_path],
               'task_dep': ['jshat_deps']}


def task_homepage_docs():
    """Homepage - copy docs files"""
    return {'actions': [(common.rm_rf, [docs_dst_dir]),
                        (common.cp_r, [docs_src_dir, docs_dst_dir])],
            'task_dep': ['docs']}
