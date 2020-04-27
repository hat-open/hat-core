"""Event server main

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
import hat.event.common
import hat.event.server.backend_engine
import hat.event.server.communication
import hat.event.server.module_engine
import hat.monitor.client
import hat.monitor.common


user_conf_dir = Path(appdirs.user_config_dir('hat'))

default_conf_path = user_conf_dir / 'event.yaml'


def main():
    """Main"""
    aio.init_asyncio()

    args = _create_parser().parse_args()
    conf = json.decode_file(args.conf)
    json_schema_repo = json.SchemaRepository(
        args.schemas_json_path, *args.additional_json_schemas_paths)
    json_schema_repo.validate('hat://event/main.yaml#', conf)
    sub_confs = ([conf['backend_engine']['backend']] +
                 conf['module_engine']['modules'])
    for sub_conf in sub_confs:
        module = importlib.import_module(sub_conf['module'])
        json_schema_id = module.json_schema_id
        if json_schema_id:
            json_schema_repo.validate(json_schema_id, sub_conf)

    logging.config.dictConfig(conf['log'])

    sbs_repo = create_sbs_repo(args.schemas_sbs_path)

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf, sbs_repo))


def create_sbs_repo(schemas_sbs_path):
    """Create event server SBS repository

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
        conf (json.Data): configuration defined by ``hat://event/main.yaml#``
        sbs_repo (hat.sbs.Repository): event SBS repository

    """
    run_cb = functools.partial(run, conf, sbs_repo)
    await hat.monitor.client.run_component(conf['monitor'], sbs_repo, run_cb)


async def run(conf, sbs_repo, monitor):
    """Run

    Args:
        conf (json.Data): configuration defined by ``hat://event/main.yaml#``
        sbs_repo (hat.sbs.Repository): event SBS repository
        monitor (hat.monitor.client.Client): monitor client

    """
    async_group = aio.Group()
    backend_engine = None
    module_engine = None
    communication = None
    try:
        backend_engine = await hat.event.server.backend_engine.create(
            conf['backend_engine'], sbs_repo)
        async_group.spawn(aio.call_on_cancel,
                          backend_engine.async_close)

        module_engine = await hat.event.server.module_engine.create(
            conf['module_engine'], backend_engine)
        async_group.spawn(aio.call_on_cancel,
                          module_engine.async_close)

        communication = await hat.event.server.communication.create(
            conf['communication'], sbs_repo, module_engine)
        async_group.spawn(aio.call_on_cancel,
                          communication.async_close)

        wait_futures = [backend_engine.closed,
                        module_engine.closed,
                        communication.closed]
        await asyncio.wait(wait_futures, return_when=asyncio.FIRST_COMPLETED)
    finally:
        await aio.uncancellable(async_group.async_close())
        await asyncio.sleep(0.1)


def _create_parser():
    parser = argparse.ArgumentParser(prog='hat-event')
    parser.add_argument(
        '--conf', metavar='path', dest='conf',
        default=default_conf_path,
        action=util.EnvPathArgParseAction,
        help="configuration defined by hat://event/main.yaml# "
             "(default $XDG_CONFIG_HOME/hat/event.yaml)")
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
