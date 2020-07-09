import sys
import argparse
from pathlib import Path
from PySide2.QtWidgets import QApplication

from hat import util
from hat.peg_browser import window


default_ui_path = Path(__file__).parent / 'ui'
default_fonts_path = Path(__file__).parent / 'fonts'


def main():
    args = _create_parser().parse_args()
    app = QApplication(sys.argv)
    proxy = window.MainProxy(args.ui_path, args.fonts_path)
    window.create(args.ui_path, proxy)
    return app.exec_()


def _create_parser():
    parser = argparse.ArgumentParser(prog='hat-peg-browser')
    dev_args = parser.add_argument_group('development arguments')
    dev_args.add_argument(
        '--fonts-path', metavar='path', dest='fonts_path',
        default=default_fonts_path,
        action=util.EnvPathArgParseAction,
        help="override fonts directory path")
    dev_args.add_argument(
        '--ui-path', metavar='path', dest='ui_path',
        default=default_ui_path,
        action=util.EnvPathArgParseAction,
        help="override web ui directory path")
    dev_args.add_argument(
        '--remote-debugging-port', metavar='port',
        default=None,
        help="remote debugging port")
    return parser


if __name__ == '__main__':
    sys.exit(main())
