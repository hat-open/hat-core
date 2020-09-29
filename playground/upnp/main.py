import sys
import pprint
import asyncio

from hat.util import aio
from hat.drivers import upnp


def main():
    aio.init_asyncio()
    aio.run_asyncio(async_main())


async def async_main():

    locations = set()

    async def on_device_info(info):
        if info.location in locations:
            return
        locations.add(info.location)
        description = await upnp.get_description(info.location)
        print('*' * 50)
        pprint.pprint(description)

    srv = await upnp.discover(on_device_info)
    await asyncio.sleep(5)
    await srv.async_close()


if __name__ == '__main__':
    sys.exit(main())
