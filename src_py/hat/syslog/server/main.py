"""Syslog Server main module"""

import asyncio
import contextlib
import logging.config
import sys

from hat import aio
from hat.syslog.server.backend import create_backend
from hat.syslog.server.conf import (Conf, get_conf)
from hat.syslog.server.syslog import create_syslog_server
from hat.syslog.server.ui import create_web_server


mlog: logging.Logger = logging.getLogger('hat.syslog.server.main')
"""Module logger"""


def main():
    """Syslog Server main"""
    aio.init_asyncio()
    conf = get_conf()
    logging.config.dictConfig(conf.log)
    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf))


async def async_main(conf: Conf):
    """Syslog Server async main"""
    backend = None
    web_server = None
    syslog_server = None
    try:
        mlog.debug("creating backend...")
        backend = await create_backend(conf.db)

        mlog.debug("creating web server...")
        web_server = await create_web_server(conf.ui, backend)

        mlog.debug("creating syslog server...")
        syslog_server = await create_syslog_server(conf.syslog, backend)

        mlog.debug("initialization done")
        async with aio.Group() as group:
            await asyncio.wait([group.spawn(backend.wait_closed),
                                group.spawn(web_server.wait_closed),
                                group.spawn(syslog_server.wait_closed)],
                               return_when=asyncio.FIRST_COMPLETED)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        mlog.fatal("error during initialization: %s", e, exc_info=e)
        raise
    finally:
        mlog.debug("closing services...")
        futures = [i.async_close()
                   for i in [syslog_server, web_server, backend]
                   if i]
        if futures:
            done, pending = await asyncio.wait(futures, timeout=2)
        for i in done:
            i.result()
        if pending:
            raise Exception("could not shut down all services")
        mlog.debug("services closed")
        await asyncio.sleep(0.5)


if __name__ == '__main__':
    sys.exit(main())
