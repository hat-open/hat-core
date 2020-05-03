"""Translator main

Attributes:
    builtin_translators (List[hat.translator.common.Translator]):
        builtin translators

"""

import argparse
import importlib
import itertools
import sys

from hat import util
from hat.util import json


builtin_translators = []


def main():
    """Main"""
    args = _create_parser().parse_args()

    json_schema_repo = json.SchemaRepository(
        json.json_schema_repo, *args.additional_json_schemas_paths)
    translators = []
    for module in itertools.chain(builtin_translators, args.module_names):
        translators += importlib.import_module(module).translators
    format = {'yaml': json.Format.YAML,
              'json': json.Format.JSON}[args.format]

    if args.action == 'list':
        output = [_translator_to_json(trans) for trans in translators]

    elif args.action == 'translate':
        trans = util.first(translators[::-1],
                           lambda i: i.input_type == args.input_type and
                           i.output_type == args.output_type)
        if not trans:
            raise Exception('translator not found')
        input_conf = json.decode(sys.stdin.read(), format=format)
        if trans.input_schema:
            json_schema_repo.validate(trans.input_schema, input_conf)
        output = trans.translate(input_conf)
        if trans.output_schema:
            json_schema_repo.validate(trans.output_schema, output)

    else:
        raise NotImplementedError()

    print(json.encode(output, format=format, indent=4))


def _translator_to_json(trans):
    return {k: v for k, v in trans._asdict().items() if k != 'translate'}


def _create_parser():

    def add_global_arguments(parser):
        parser.add_argument(
            '--module', metavar='name', dest='module_names', nargs='*',
            default=[],
            help="additional translators module name")
        parser.add_argument(
            '--additional-json-schemas-path', metavar='path',
            dest='additional_json_schemas_paths', nargs='*', default=[],
            action=util.EnvPathArgParseAction,
            help="additional json schemas paths")
        parser.add_argument(
            '--format', metavar='format', dest='format',
            choices=['yaml', 'json'], default='yaml',
            help="input/output format: 'yaml' or 'json' (default 'yaml')")

    parser = argparse.ArgumentParser(prog='hat-translator')
    subparsers = parser.add_subparsers(dest='action', required=True)

    translate_parser = subparsers.add_parser(
        'translate', help='translate stdin input to stdout output')
    add_global_arguments(translate_parser)
    translate_parser.add_argument(
        '--input-type', metavar='type', dest='input_type', required=True,
        help="input configuration type")
    translate_parser.add_argument(
        '--output-type', metavar='type', dest='output_type', required=True,
        help="output configuration type")

    list_parser = subparsers.add_parser(
        'list', help='list available translations')
    add_global_arguments(list_parser)

    return parser


if __name__ == '__main__':
    sys.exit(main())
