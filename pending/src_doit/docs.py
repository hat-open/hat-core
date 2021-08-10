from pathlib import Path
import subprocess
import sys

from hat import asn1
from hat.doit import common


__all__ = ['task_docs',
           'task_docs_pyhat',
           'task_docs_jshat',
           'task_docs_asn1']


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
