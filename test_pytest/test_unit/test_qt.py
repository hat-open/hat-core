import threading

from hat import qt


def test_example_docs():

    async def async_main(executor):
        asyncio_tid = threading.get_ident()
        result = await executor(threading.get_ident)
        assert result == qt_tid
        assert asyncio_tid != qt_tid

    qt_tid = threading.get_ident()
    qt.run(async_main)
