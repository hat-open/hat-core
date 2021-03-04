import asyncio
import contextlib

from hat import aio
from hat.drivers import cdt


# chromium --headless --remote-debugging-port=9222


def main():
    aio.init_asyncio()
    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main())


async def async_main():
    conn = await cdt.connect('127.0.0.1', 9222)

    result = await conn.call('Target.createTarget', {'url': 'abaout:blank'})
    page_id = result['targetId']

    result = await conn.call('Target.attachToTarget', {'targetId': page_id,
                                                       'flatten': True})
    session_id = result['sessionId']

    result = await conn.call('Runtime.evaluate',
                             {'expression': 'JSON.stringify([1, 2, 3])'},
                             session_id=session_id)
    print(result)

    await conn.call('Target.closeTarget', {'targetId': page_id})

    await conn.async_close()


if __name__ == '__main__':
    main()
