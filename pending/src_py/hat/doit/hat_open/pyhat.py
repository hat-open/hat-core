
fonts_dir = Path('fonts')
src_asn1_dir = Path('schemas_asn1')


def task_pyhat_build_peg_browser():
    """PyHat - build hat-peg-browser"""

    def mappings():
        dst_dir = _get_build_dst_dir('hat-peg-browser')
        jshat_build = Path('build/jshat/peg_browser')
        for i in (src_py_dir / 'hat/peg_browser').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        for i in jshat_build.rglob('*'):
            if i.is_dir():
                continue
            yield i, (dst_dir / 'hat/peg_browser/ui'
                              / i.relative_to(jshat_build))
        for i in ['RobotoMono/RobotoMono-Regular.ttf']:
            yield fonts_dir / i, dst_dir / 'hat/peg_browser/fonts/' / i

    return dict(
        _get_task_build(
            name='hat-peg-browser',
            description='Hat PEG browser',
            dependencies=['Pillow',
                          'PySide2',
                          'hat-util',
                          'hat-peg'],
            mappings=mappings,
            gui_scripts=['hat-peg-browser = hat.peg_browser.main:main']),
        task_dep=['jshat_build'])
