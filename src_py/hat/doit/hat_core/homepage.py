from pathlib import Path
import xml.etree.ElementTree

from hat.doit import common
from hat.doit import tmpl
from hat.doit.hat_core.articles import dst_dir as articles_src_dir
from hat.doit.hat_core.docs import html_dst_dir as docs_src_dir


__all__ = ['task_homepage',
           'task_homepage_pages',
           'task_homepage_static',
           'task_homepage_sass',
           'task_homepage_docs',
           'task_homepage_articles']


src_dir = Path('homepage')
dst_dir = Path('build/homepage')
docs_dst_dir = dst_dir / 'docs'
articles_dst_dir = dst_dir / 'articles'


def task_homepage():
    """Homepage - build"""
    return {'actions': None,
            'task_dep': ['homepage_pages',
                         'homepage_static',
                         'homepage_sass',
                         'homepage_docs',
                         'homepage_articles']}


def task_homepage_pages():
    """Homepage - build pages"""
    for i in src_dir.rglob('*.html'):
        if i.stem.startswith('_'):
            continue
        name = i.relative_to(src_dir).with_suffix('').as_posix()
        page = Page(name)
        yield {'name': str(page.dst_path),
               'actions': [page.build],
               'targets': [page.dst_path],
               'task_dep': ['homepage_articles']}


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


def task_homepage_articles():
    """Homepage - copy articles"""
    return {'actions': [(common.rm_rf, [articles_dst_dir]),
                        (common.cp_r, [articles_src_dir, articles_dst_dir])],
            'task_dep': ['articles']}


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
            'download': 'Download',
            'articles': 'Articles'
        }.get(self._name)

    @property
    def links(self):
        return [
            {'label': 'About',
             'path': 'index.html'},
            {'label': 'Download',
             'path': 'download.html'},
            {'label': 'Articles',
             'path': 'articles.html'},
            {'label': 'Documentation',
             'path': 'docs/index.html'},
            {'label': 'Source',
             'path': 'https://github.com/hat-open/hat-core'}
        ]

    @property
    def components(self):
        return [
            {'title': 'hat-orchestrator',
             'description': 'Simple cross-platform daemon/service manager'},
            {'title': 'hat-monitor',
             'description': 'Redundancy and service discovery server'},
            {'title': 'hat-event',
             'description': 'Event pub/sub communication and storage'},
            {'title': 'hat-gateway',
             'description': 'Remote communication device gateway'},
            {'title': 'hat-gui',
             'description': 'GUI server'},
            {'title': 'hat-translator',
             'description': 'Configuration transformation interface'},
            {'title': 'hat-syslog',
             'description': 'Syslog server'}
        ]

    @property
    def python_libraries(self):
        return [
            {'title': 'hat-util',
             'description': 'Utility modules'},
            {'title': 'hat-peg',
             'description': 'Parsing expression grammar'},
            {'title': 'hat-sbs',
             'description': 'Simple binary serialization'},
            {'title': 'hat-chatter',
             'description': 'Chatter communication protocol'},
            {'title': 'hat-juggler',
             'description': 'Juggler communication protocol'},
            {'title': 'hat-duktape',
             'description': 'Python Duktape JS wrapper'},
            {'title': 'hat-sqlite3',
             'description': 'Hat specific sqlite3 build'},
            {'title': 'hat-asn1',
             'description': 'ASN.1 parser and encoder'},
            {'title': 'hat-drivers',
             'description': 'Communication drivers'}
        ]

    @property
    def javascript_libraries(self):
        return [
            {'title': '@hat-core/util',
             'description': 'Utility module'},
            {'title': '@hat-core/renderer',
             'description': 'Virtual DOM renderer'},
            {'title': '@hat-core/future',
             'description': 'Async Future implementation'},
            {'title': '@hat-core/juggler',
             'description': 'Juggler client library'}
        ]

    @property
    def python_packages(self):
        return ['hat-util',
                'hat-peg',
                'hat-sbs',
                'hat-chatter',
                'hat-juggler',
                'hat-duktape',
                'hat-sqlite3',
                'hat-asn1',
                'hat-drivers',
                'hat-orchestrator',
                'hat-monitor',
                'hat-event',
                'hat-gateway',
                'hat-gui',
                'hat-translator',
                'hat-syslog']

    @property
    def javascript_packages(self):
        return ['@hat-core/util',
                '@hat-core/renderer',
                '@hat-core/future',
                '@hat-core/juggler']

    def get_articles(self):
        ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
        for i in sorted(articles_dst_dir.glob('*.html')):
            root = xml.etree.ElementTree.parse(str(i)).getroot()
            title_tag = root.find("./xhtml:head/xhtml:title", ns)
            author_tag = root.find("./xhtml:head/xhtml:meta[@name='author']",
                                   ns)
            date_tag = root.find("./xhtml:head/xhtml:meta[@name='date']", ns)
            title = title_tag.text
            author = (author_tag.get('content')
                      if author_tag is not None else None)
            date = date_tag.get('content') if date_tag is not None else None
            yield {'link': f'articles/{i.name}',
                   'title': title,
                   'author': author,
                   'date': date}

    def build(self):
        tmpl.mako_build(src_dir, self.src_path, self.dst_path, {'page': self})
