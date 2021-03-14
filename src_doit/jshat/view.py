from pathlib import Path
import functools
import subprocess
import tempfile

from hat.doit import common


__all__ = ['task_jshat_view',
           'task_jshat_view_login']


build_dir = Path('build/jshat/view')
static_dir = Path('static_web/view')
src_js_dir = Path('src_js')
src_scss_dir = Path('src_scss')
node_modules_dir = Path('node_modules')


def task_jshat_view():
    """JsHat view - build all"""
    return {'actions': None,
            'task_dep': ['jshat_view_login']}


def task_jshat_view_login():
    """JsHat view - build login"""
    return _get_task_build('login',
                           src_js_dir / '@hat-core/views/login/main.js')


def _get_task_build(name, entry, task_dep=[]):
    return {'actions': [functools.partial(_build_view, name, entry)],
            'pos_arg': 'args',
            'task_dep': ['jshat_deps',
                         *task_dep]}


def _build_view(name, entry, args):
    args = args or []
    conf = _webpack_conf.format(
        name=name,
        entry=entry.resolve(),
        build_dir=build_dir.resolve(),
        src_js_dir=src_js_dir.resolve(),
        src_scss_dir=src_scss_dir.resolve(),
        node_modules_dir=node_modules_dir.resolve())

    dst_dir = build_dir / name
    dst_dir.mkdir(parents=True, exist_ok=True)

    app_static_dir = static_dir / name
    for i in app_static_dir.glob('*'):
        common.cp_r(i, dst_dir / i.relative_to(app_static_dir))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config_path = tmpdir / 'webpack.config.js'
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(conf)
        subprocess.run([str(node_modules_dir / '.bin/webpack'),
                        '--config', str(config_path),
                        *args],
                       check=True)


_webpack_conf = r"""
module.exports = {{
    mode: 'none',
    entry: '{entry}',
    output: {{
        libraryTarget: 'commonjs',
        filename: 'index.js',
        path: '{build_dir}/{name}'
    }},
    module: {{
        rules: [
            {{
                test: /\.scss$/,
                use: [
                    "style-loader",
                    "css-loader",
                    "resolve-url-loader",
                    {{
                        loader: "sass-loader",
                        options: {{ sourceMap: true }}
                    }}
                ]
            }}
        ]
    }},
    resolve: {{
        modules: [
            '{src_js_dir}',
            '{src_scss_dir}/view',
            '{node_modules_dir}'
        ]
    }},
    watchOptions: {{
        ignored: /node_modules/
    }},
    devtool: 'eval-source-map',
    stats: 'errors-only'
}};
"""
