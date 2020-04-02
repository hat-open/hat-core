from pathlib import Path

from hat.doit import common
from hat.doit import tmpl
from hat.doit.hat_core.docs import html_dst_dir as docs_src_dir


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
        page = Page(name)
        yield {'name': str(page.dst_path),
               'actions': [page.build],
               'targets': [page.dst_path]}


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
                           f'sassc {src_path} {dst_path}'],
               'targets': [dst_path]}


def task_homepage_docs():
    """Homepage - copy docs files"""
    return {'actions': [(common.rm_rf, [docs_dst_dir]),
                        (common.cp_r, [docs_src_dir, docs_dst_dir])],
            'task_dep': ['docs_html']}


class Page:

    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def src_path(self):
        return src_dir / f"{self._name}.html"

    @property
    def dst_path(self):
        return dst_dir / f"{self._name}.html"

    @property
    def title(self):
        return {
            'index': 'About',
            'download': 'Download'
        }.get(self._name)

    @property
    def links(self):
        return [
            {'icon': 'fa-home',
             'label': 'About',
             'path': 'index.html'},
            {'icon': 'fa-download',
             'label': 'Download',
             'path': 'download.html'},
            {'icon': 'fa-book',
             'label': 'Documentation',
             'path': 'docs/index.html'},
            {'icon': 'fa-github',
             'label': 'Source',
             'path': 'https://github.com/hat-open/hat-core'}
        ]

    @property
    def components(self):
        return []

    @property
    def python_libraries(self):
        return [
            {'title': 'hat-util',
             'description': 'Utility modules'},
            {'title': 'hat-peg',
             'description': 'Parsing expression grammar'},
            {'title': 'hat-juggler',
             'description': 'Juggler communication protocol'},
        ]

    @property
    def javascript_libraries(self):
        return []

    @property
    def python_packages(self):
        return [{'name': 'hat-util',
                 'docs': 'docs/libraries/util.html'},
                {'name': 'hat-peg',
                 'docs': 'docs/libraries/peg.html'},
                {'name': 'hat-juggler',
                 'docs': 'docs/libraries/juggler.html'}]

    @property
    def javascript_packages(self):
        return []

    def build(self):
        tmpl.mako_build(src_dir, self.src_path, self.dst_path, {'page': self})
