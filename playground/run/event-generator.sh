#!/bin/sh

. ./env.sh

exec $PYTHON << EOF
import asyncio
import contextlib

from hat import aio
from hat.event import common
import hat.event.client

def main():
    aio.init_asyncio()
    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main())

async def async_main():
    conn = await hat.event.client.connect('tcp+sbs://127.0.0.1:23012')
    try:
        await conn.register_with_response([common.RegisterEvent(
            event_type=('a', 'b', 'c'),
            source_timestamp=common.now(),
            payload=common.EventPayload(
                type=common.EventPayloadType.JSON,
                data=123))])
    finally:
        await conn.async_close()

main()
EOF
