from pathlib import Path
import io

from hat.util import json
from hat.gui import vt

__all__ = ['task_jshat_assets',
           'task_jshat_assets_hue_browser']


jshat_dir = Path('src_js')
node_modules_dir = Path('node_modules')


def task_jshat_assets():
    """JsHat assets - build all"""
    return {'actions': None,
            'task_dep': ['jshat_assets_hue_browser']}


def task_jshat_assets_hue_browser():
    """JsHat assets - build all"""
    def mappings():
        yield 'bars', node_modules_dir / 'svg-loaders/svg-css-loaders/bars.svg'

    return _get_task_assets(jshat_dir / '@hat-core/hue-manager/assets.js',
                            mappings)


def _get_task_assets(dst_path, mappings):
    src_paths = [src_path for _, src_path in mappings()]
    return {'actions': [(_build_assets, [dst_path, mappings])],
            'file_dep': src_paths,
            'targets': [dst_path]}


def _build_assets(dst_path, mappings):
    assets = {name: _build_asset(src_path) for name, src_path in mappings()}
    assets_str = json.encode(assets)
    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(f'export default {assets_str};')


def _build_asset(src_path):
    with open(src_path, encoding='utf-8') as f:
        src = f.read()

    if src_path.suffix == '.svg':
        return vt.parse(io.StringIO(src))

    return src
