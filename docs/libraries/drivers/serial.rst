.. _hat-drivers-serial:

`hat.drivers.serial` - Serial communication
===========================================

Serial port communication driver based on
`pyserial <https://pypi.org/project/pyserial/>`_ with addition of
asyncio wrapper.

::

    async def create(port: str, *,
                     baudrate: int = 9600,
                     bytesize: ByteSize = ByteSize.EIGHTBITS,
                     parity: Parity = Parity.NONE,
                     stopbits: StopBits = StopBits.ONE,
                     rtscts: bool = False,
                     dsrdtr: bool = False,
                     silent_interval: float = 0
                     ) -> 'Connection': ...

    class Connection(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

        async def read(self, size: int) -> bytes: ...

        async def write(self, data: bytes): ...

Example usage::

    # create null-modem with socat
    tmp_path = pathlib.Path('.')
    path1 = tmp_path / '1'
    path2 = tmp_path / '2'
    p = subprocess.Popen(['socat',
                          f'pty,link={path1},raw,echo=0',
                          f'pty,link={path2},raw,echo=0'])
    while not path1.exists() or not path2.exists():
        asyncio.sleep(0.001)

    # create two connections (one for each null-modem end)
    conn1 = await hat.drivers.serial.create(port=str(path1),
                                            rtscts=True,
                                            dsrdtr=True)
    conn2 = await hat.drivers.serial.create(port=str(path2),
                                            rtscts=True,
                                            dsrdtr=True)

    # send from conn1 to conn2
    data = b'test1'
    await conn1.write(data)
    assert data == await conn2.read(len(data))

    # send from conn2 to conn1
    data = b'test2'
    await conn2.write(data)
    assert data == await conn1.read(len(data))

    # close connections
    await conn1.async_close()
    await conn2.async_close()

    # close null-modem
    p.terminate()


API
---

API reference is available as part of generated documentation:

    * `Python hat.drivers.serial module <../../pyhat/hat/drivers/serial.html>`_
