"""Translator main

Attributes:
    builtin_translators (List[hat.translator.common.Translator]):
        builtin translators

"""

from pathlib import Path
import argparse
import importlib
import itertools
import sys

from hat import json
from hat import util


builtin_translators = []


def main():
    """Main"""
    args = _create_parser().parse_args()
    json_format = {'yaml': json.Format.YAML,
                   'json': json.Format.JSON}[args.format]

    if args.action == 'list':
        output = act_list(module_names=args.module_names)

    elif args.action == 'translate':
        json_schema_repo = json.SchemaRepository(
            json.json_schema_repo, *args.additional_json_schemas_paths)
        input_conf = json.decode(sys.stdin.read(), format=json_format)
        output = act_translate(module_names=args.module_names,
                               json_schema_repo=json_schema_repo,
                               input_type=args.input_type,
                               output_type=args.output_type,
                               input_conf=input_conf)

    else:
        raise NotImplementedError()

    print(json.encode(output, format=json_format, indent=4))


def act_list(module_names):
    """List action

    Args:
        module_names (List[str]): python module names with translator
            definitions

    Returns:
        json.Data

    """
    translators = _get_translators(module_names)
    return [{k: v for k, v in trans._asdict().items() if k != 'translate'}
            for trans in translators]


def act_translate(module_names, json_schema_repo, input_type,
                  output_type, input_conf):
    """Translate action

    Args:
        module_names (List[str]): python module names with translator
            definitions
        json_schema_repo (json.SchemaRepository): json schemas repository
        input_type (str): input configuration type identifier
        output_type (str): output configuration type identifier
        input_conf (json.Data): input configuration

    Returns:
        json.Data

    """
    translators = _get_translators(module_names)
    trans = util.first(translators[::-1],
                       lambda i: i.input_type == input_type and
                       i.output_type == output_type)
    if not trans:
        raise Exception('translator not found')
    if trans.input_schema:
        json_schema_repo.validate(trans.input_schema, input_conf)
    output = trans.translate(input_conf)
    if trans.output_schema:
        json_schema_repo.validate(trans.output_schema, output)
    return output


def _get_translators(module_names):
    translators = []
    for module in itertools.chain(builtin_translators, module_names):
        translators += importlib.import_module(module).translators
    return translators


def _create_parser():

    def add_global_arguments(parser):
        parser.add_argument(
            '--module', metavar='name', dest='module_names', nargs='*',
            default=[],
            help="additional translators module name")
        parser.add_argument(
            '--additional-json-schemas-path', metavar='path', type=Path,
            dest='additional_json_schemas_paths', nargs='*', default=[],
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
