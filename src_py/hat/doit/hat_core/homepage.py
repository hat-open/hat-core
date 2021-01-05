from pathlib import Path
import xml.etree.ElementTree

from hat.doit import common
from hat.doit.hat_core.articles import dst_dir as articles_src_dir
from hat.doit.hat_core.articles import get_article_names
from hat.doit.hat_core.docs import dst_dir as docs_src_dir


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
        src_path = src_dir / f"{name}.html"
        dst_path = dst_dir / f"{name}.html"
        params = {'get_articles': _get_articles}
        yield {'name': str(dst_path),
               'actions': [(common.mako_build, [src_dir, src_path, dst_path,
                                                params])],
               'targets': [dst_path],
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
            'task_dep': ['docs']}


def task_homepage_articles():
    """Homepage - copy articles"""

    def copy_article(name):
        common.rm_rf(articles_dst_dir / name)
        common.cp_r(articles_src_dir / name, articles_dst_dir / name)

    return {'actions': [(copy_article, [name])
                        for name in get_article_names()],
            'task_dep': ['articles']}


def _get_articles():
    ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
    for name in sorted(get_article_names()):
        rst_path = articles_src_dir / f'{name}/index.html'
        root = xml.etree.ElementTree.parse(str(rst_path)).getroot()
        title_tag = root.find("./xhtml:head/xhtml:title", ns)
        author_tag = root.find("./xhtml:head/xhtml:meta[@name='author']",
                               ns)
        date_tag = root.find("./xhtml:head/xhtml:meta[@name='date']", ns)
        title = title_tag.text
        author = (author_tag.get('content')
                  if author_tag is not None else None)
        date = date_tag.get('content') if date_tag is not None else None
        yield {'link': f'articles/{name}/index.html',
               'title': title,
               'author': author,
               'date': date}
