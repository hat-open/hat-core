from pathlib import Path

from hat import asn1
from hat.doit import common
import hat.doit.docs


__all__ = ['task_docs',
           'task_docs_jshat',
           'task_docs_asn1']


src_dir = Path('docs')
dst_dir = Path('build/docs')
asn1_dir = Path('schemas_asn1')
jshat_dst_dir = dst_dir / 'jshat'
asn1_dst_dir = dst_dir / 'asn1'


def task_docs():
    """Docs - build documentation"""
    return {'actions': [(hat.doit.docs.sphinx_build, [
                            hat.doit.docs.SphinxOutputType.HTML,
                            src_dir,
                            dst_dir])],
            'task_dep': ['cache_tools_plantuml',
                         'duktape',
                         'pymod',
                         'schemas',
                         'docs_jshat',
                         'docs_asn1']}


def task_docs_jshat():
    """Docs - build jshat documentation"""
    return {'actions': [(common.mkdir_p, [jshat_dst_dir.parent]),
                        'yarn run --silent docs'],
            'task_dep': ['jshat_deps']}


def task_docs_asn1():
    """Docs - build asn1 documentation"""
    src_paths = list(asn1_dir.rglob('*.asn'))
    dst_path = asn1_dst_dir / 'doc.html'

    def build():
        repo = asn1.Repository(*src_paths)
        doc = repo.generate_html_doc()
        asn1_dst_dir.mkdir(parents=True, exist_ok=True)
        with open(dst_path, 'w', encoding='utf-8') as f:
            f.write(doc)

    return {'actions': [build],
            'file_dep': src_paths,
            'targets': [dst_path]}
