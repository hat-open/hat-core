"""Event server main

Attributes:
    user_conf_dir (Path): configuration directory
    default_conf_path (Path): default configuration path

"""

from pathlib import Path
import argparse
import asyncio
import contextlib
import importlib
import logging.config
import sys

import appdirs

from hat import aio
from hat import json
from hat.event.server import common
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
    common.json_schema_repo.validate('hat://event/main.yaml#', conf)
    sub_confs = ([conf['backend_engine']['backend']] +
                 conf['module_engine']['modules'])
    for sub_conf in sub_confs:
        module = importlib.import_module(sub_conf['module'])
        if module.json_schema_repo and module.json_schema_id:
            module.json_schema_repo.validate(module.json_schema_id, sub_conf)

    logging.config.dictConfig(conf['log'])

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf))


async def async_main(conf):
    """Async main

    Args:
        conf (json.Data): configuration defined by ``hat://event/main.yaml#``

    """
    monitor = await hat.monitor.client.connect(conf['monitor'])
    try:
        await hat.monitor.client.run_component(monitor, run, conf, monitor)
    finally:
        await aio.uncancellable(monitor.async_close())


async def run(conf, monitor):
    """Run

    Args:
        conf (json.Data): configuration defined by ``hat://event/main.yaml#``
        monitor (hat.monitor.client.Client): monitor client

    """
    async_group = aio.Group()
    backend_engine = None
    module_engine = None
    communication = None
    try:
        backend_engine = await hat.event.server.backend_engine.create(
            conf['backend_engine'])
        async_group.spawn(aio.call_on_cancel,
                          backend_engine.async_close)

        module_engine = await hat.event.server.module_engine.create(
            conf['module_engine'], backend_engine)
        async_group.spawn(aio.call_on_cancel,
                          module_engine.async_close)

        communication = await hat.event.server.communication.create(
            conf['communication'], module_engine)
        async_group.spawn(aio.call_on_cancel,
                          communication.async_close)

        wait_futures = [async_group.spawn(backend_engine.wait_closed),
                        async_group.spawn(module_engine.wait_closed),
                        async_group.spawn(communication.wait_closed)]
        await asyncio.wait(wait_futures, return_when=asyncio.FIRST_COMPLETED)
    finally:
        await aio.uncancellable(async_group.async_close())
        await asyncio.sleep(0.1)


def _create_parser():
    parser = argparse.ArgumentParser(prog='hat-event')
    parser.add_argument(
        '--conf', metavar='path', dest='conf',
        default=default_conf_path, type=Path,
        help="configuration defined by hat://event/main.yaml# "
             "(default $XDG_CONFIG_HOME/hat/event.yaml)")
    return parser


if __name__ == '__main__':
    sys.exit(main())
