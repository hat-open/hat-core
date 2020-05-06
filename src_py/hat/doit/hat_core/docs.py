from pathlib import Path

from hat import asn1
import hat.doit.docs


__all__ = ['task_docs',
           'task_docs_html',
           'task_docs_latex',
           'task_docs_pdf',
           'task_docs_jshat',
           'task_docs_asn1']


src_dir = Path('docs')
dst_dir = Path('build/docs')
asn1_dir = Path('schemas_asn1')
html_dst_dir = dst_dir / 'html'
latex_dst_dir = dst_dir / 'latex'
pdf_dst_dir = dst_dir / 'pdf'
jshat_dst_dir = dst_dir / 'jshat'
asn1_dst_dir = dst_dir / 'asn1'


def task_docs():
    """Docs - build documentation"""
    return {'actions': None,
            'task_dep': ['docs_html',
                         'docs_pdf',
                         'docs_jshat',
                         'docs_asn1']}


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


def task_docs_asn1():
    """Docs - build asn1 documentation"""

    def build():
        repo = asn1.Repository(asn1_dir)
        doc = repo.generate_html_doc()
        asn1_dst_dir.mkdir(parents=True, exist_ok=True)
        with open(asn1_dst_dir / 'doc.html', 'w', encoding='utf-8') as f:
            f.write(doc)

    return {'actions': [build]}
