#!/bin/sh

. ./env.sh

exec $PYTHON << EOF
import asyncio
import contextlib

from hat import aio
import hat.monitor.client

def main():
    aio.init_asyncio()
    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main())

async def async_main():
    conn = await hat.monitor.client.connect({
        'name': 'name',
        'group': 'group',
        'monitor_address': 'tcp+sbs://127.0.0.1:23010',
        'component_address': 'address'})
    try:
        await conn.wait_closing()
    finally:
        await conn.async_close()

main()
EOF
