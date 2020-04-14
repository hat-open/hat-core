from pathlib import Path

import hat.doit.docs


__all__ = ['task_docs',
           'task_docs_html',
           'task_docs_latex',
           'task_docs_pdf',
           'task_docs_jshat']


src_dir = Path('docs')
dst_dir = Path('build/docs')
html_dst_dir = dst_dir / 'html'
latex_dst_dir = dst_dir / 'latex'
pdf_dst_dir = dst_dir / 'pdf'
jshat_dst_dir = dst_dir / 'jshat'


def task_docs():
    """Docs - build documentation"""
    return {'actions': None,
            'task_dep': ['docs_html',
                         'docs_pdf',
                         'docs_jshat']}


def task_docs_html():
    """Docs - build HTML documentation"""
    return {'actions': [(hat.doit.docs.sphinx_build, [
                            hat.doit.docs.SphinxOutputType.HTML,
                            src_dir,
                            html_dst_dir])],
            'task_dep': ['cache_tools_plantuml']}


def task_docs_latex():
    """Docs - build LaTeX documentation"""
    return {'actions': [(hat.doit.docs.sphinx_build, [
                            hat.doit.docs.SphinxOutputType.LATEX,
                            src_dir,
                            latex_dst_dir])],
            'task_dep': ['cache_tools_plantuml']}


def task_docs_pdf():
    """Docs - build PDF documentation"""
    return {'actions': [(hat.doit.docs.latex_build, [
                            latex_dst_dir,
                            pdf_dst_dir])] * 3,
            'task_dep': ['docs_latex']}


def task_docs_jshat():
    """Docs - build jshat documentation"""
    return {'actions': ['yarn run --silent docs'],
            'task_dep': ['jshat_deps']}
