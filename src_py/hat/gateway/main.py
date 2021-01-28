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

from hat import aio
from hat import json
import hat.event.client
import hat.event.common
import hat.gateway.common
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
    hat.gateway.common.json_schema_repo.validate('hat://gateway/main.yaml#',
                                                 conf)
    for device_conf in conf['devices']:
        module = importlib.import_module(device_conf['module'])
        if module.json_schema_repo and module.json_schema_id:
            module.json_schema_repo.validate(module.json_schema_id,
                                             device_conf)

    logging.config.dictConfig(conf['log'])

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf))


async def async_main(conf):
    """Async main

    Args:
        conf (json.Data): configuration defined by ``hat://gateway/main.yaml#``

    """
    monitor = await hat.monitor.client.connect(conf['monitor'])
    try:
        await hat.monitor.client.run_component(
            monitor, run_with_monitor, conf, monitor)
    finally:
        await aio.uncancellable(monitor.async_close())


async def run_with_monitor(conf, monitor):
    """Run with monitor client

    Args:
        conf (json.Data): configuration defined by ``hat://gateway/main.yaml#``
        monitor (hat.monitor.client.Client): monitor client

    """
    run_cb = functools.partial(run_with_event, conf)
    await hat.event.client.run_client(
        monitor, conf['event_server_group'], run_cb,
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
        await engine.wait_closed()
    finally:
        if engine:
            await aio.uncancellable(engine.async_close())


def _create_parser():
    parser = argparse.ArgumentParser(prog='hat-gateway')
    parser.add_argument(
        '--conf', metavar='path', dest='conf',
        default=default_conf_path, type=Path,
        help="configuration defined by hat://gateway/main.yaml# "
             "(default $XDG_CONFIG_HOME/hat/gateway.yaml)")
    return parser


if __name__ == '__main__':
    sys.exit(main())
