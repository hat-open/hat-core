import threading

import pytest

from hat import qt


@pytest.mark.skip("headless not supported")
def test_example_docs():

    async def async_main(executor):
        asyncio_tid = threading.get_ident()
        result = await executor(threading.get_ident)
        assert result == qt_tid
        assert asyncio_tid != qt_tid

    qt_tid = threading.get_ident()
    qt.run(async_main)
