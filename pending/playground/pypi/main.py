import sys
import pathlib

from hat import util
from . import pypi


def main():
    util.run_asyncio(async_main())


async def async_main():
    with open('../../requirements.pip.txt', encoding='utf-8') as f:
        requirements = f.readlines()
    await pypi.download(requirements, pathlib.Path('temp'))


if __name__ == '__main__':
    sys.exit(main())
