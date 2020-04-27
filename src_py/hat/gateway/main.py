"""Gateway main

Attributes:
    user_conf_dir (Path): configuration directory
    default_conf_path (Path): default configuration path

"""

from pathlib import Path
import argparse
import asyncio
import contextlib
import functools
import importlib
import logging.config
import sys

import appdirs

from hat import sbs
from hat import util
from hat.util import aio
from hat.util import json
import hat.event.client
import hat.event.common
import hat.gateway.engine
import hat.monitor.client
import hat.monitor.common


user_conf_dir = Path(appdirs.user_config_dir('hat'))
default_conf_path = user_conf_dir / 'gateway.yaml'


def main():
    """Main"""
    aio.init_asyncio()

    args = _create_parser().parse_args()
    conf = json.decode_file(args.conf)
    json_schema_repo = json.SchemaRepository(
        args.schemas_json_path, *args.additional_json_schemas_paths)
    json_schema_repo.validate('hat://gateway/main.yaml#', conf)
    for device_conf in conf['devices']:
        module = importlib.import_module(device_conf['module'])
        json_schema_id = module.json_schema_id
        if json_schema_id:
            json_schema_repo.validate(json_schema_id, device_conf)

    logging.config.dictConfig(conf['log'])

    sbs_repo = create_sbs_repo(args.schemas_sbs_path)

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf, sbs_repo))


def create_sbs_repo(schemas_sbs_path):
    """Create gateway SBS repository

    Args:
        schemas_sbs_path (pathlib.Path): schemas_sbs path

    Returns:
        sbs.Repository

    """
    return sbs.Repository(
        hat.monitor.common.create_sbs_repo(schemas_sbs_path),
        hat.event.common.create_sbs_repo(schemas_sbs_path))


async def async_main(conf, sbs_repo):
    """Async main

    Args:
        conf (json.Data): configuration defined by ``hat://gateway/main.yaml#``
        sbs_repo (hat.sbs.Repository): gateway SBS repository

    """
    run_cb = functools.partial(run_with_monitor, conf, sbs_repo)
    await hat.monitor.client.run_component(conf['monitor'], sbs_repo, run_cb)


async def run_with_monitor(conf, sbs_repo, monitor):
    """Run with monitor client

    Args:
        conf (json.Data): configuration defined by ``hat://gateway/main.yaml#``
        sbs_repo (hat.sbs.Repository): gateway SBS repository
        monitor (hat.monitor.client.Client): monitor client

    """
    run_cb = functools.partial(run_with_event, conf)
    await hat.event.client.run_client(
        sbs_repo, monitor, conf['event_server_group'], run_cb,
        [['gateway', conf['gateway_name'], '?', '?', 'system', '*']])


async def run_with_event(conf, client):
    """Run with event client

    Args:
        conf (json.Data): configuration defined by ``hat://gateway/main.yaml#``
        client (hat.event.client.Client): event client

    """
    engine = None
    try:
        engine = await hat.gateway.engine.create_engine(conf, client)
        await engine.closed
    finally:
        if engine:
            await aio.uncancellable(engine.async_close())


def _create_parser():
    parser = argparse.ArgumentParser(prog='hat-gateway')
    parser.add_argument(
        '--conf', metavar='path', dest='conf',
        default=default_conf_path,
        action=util.EnvPathArgParseAction,
        help="configuration defined by hat://gateway/main.yaml# "
             "(default $XDG_CONFIG_HOME/hat/gateway.yaml)")
    parser.add_argument(
        '--additional-json-schemas-path', metavar='path',
        dest='additional_json_schemas_paths', nargs='*', default=[],
        action=util.EnvPathArgParseAction,
        help="additional json schemas paths")

    dev_args = parser.add_argument_group('development arguments')
    dev_args.add_argument(
        '--json-schemas-path', metavar='path', dest='schemas_json_path',
        default=json.default_schemas_json_path,
        action=util.EnvPathArgParseAction,
        help="override json schemas directory path")
    dev_args.add_argument(
        '--sbs-schemas-path', metavar='path', dest='schemas_sbs_path',
        default=sbs.default_schemas_sbs_path,
        action=util.EnvPathArgParseAction,
        help="override sbs schemas directory path")
    return parser


if __name__ == '__main__':
    sys.exit(main())
