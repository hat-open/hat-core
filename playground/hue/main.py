import sys
import pprint

from hat.util import aio
from hat.drivers import hue


def main():
    aio.init_asyncio()
    aio.run_asyncio(async_main())


async def async_main():
    with open('username.txt') as f:
        user = f.read().strip()

    conn = hue.Client('http://192.168.0.30', user)
    device_id = hue.DeviceId(hue.DeviceType.LIGHT, '1')

    # data = await conn.transport.get(None)
    # pprint.pprint(data)

    devices = await conn.get_device(device_id)
    pprint.pprint(devices)

    await conn.async_close()


if __name__ == '__main__':
    sys.exit(main())
