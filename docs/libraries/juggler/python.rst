.. _hat-juggler:

`hat.juggler` - Python juggler library
======================================

This library provides Python implementation of
:ref:`Juggler communication protocol <juggler>`.


.. _hat-juggler-connect:

Client
------

`hat.juggler.connect` coroutine creates client initiated juggler connection::

    async def connect(address: str, *,
                      autoflush_delay: typing.Optional[float] = 0.2,
                      ) -> 'Connection': ...


.. _hat-juggler-listen:
.. _hat-juggler-Server:

Server
------

`hat.juggler.listen` coroutine creates server listening for incomming
juggler  connections::

    ConnectionCb = typing.Callable[['Connection'], None]

    async def listen(host: str,
                     port: int,
                     connection_cb: ConnectionCb, *,
                     ws_path: str = '/ws',
                     static_dir: typing.Optional[pathlib.Path] = None,
                     index_path: typing.Optional[str] = '/index.html',
                     pem_file: typing.Optional[pathlib.Path] = None,
                     autoflush_delay: typing.Optional[float] = 0.2,
                     shutdown_timeout: float = 0.1
                     ) -> 'Server': ...

    class Server(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...


.. _hat-juggler-Connection:

Connection
----------

Once juggler connection is established by calling `connect` or by listening
for incoming connection with `listen`, communication interface for client-side
and for server-side is the same::

    class Connection(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

        @property
        def local_data(self) -> json.Data: ...

        @property
        def remote_data(self) -> json.Data: ...

        def register_change_cb(self,
                               cb: typing.Callable[[], None]
                               ) -> util.RegisterCallbackHandle: ...

        def set_local_data(self, data: json.Data): ...

        async def flush_local_data(self): ...

        async def send(self, msg: json.Data): ...

        async def receive(self) -> json.Data: ...


.. _hat-juggler-RpcConnection:

RpcConnection
-------------

Simple wrapper for juggler connection which provides remote procedure call
mechanics. Additional communication utilizes juggler `MESSAGE` messages::

    oneOf:
      - type: object
        required:
            - type
            - id
            - direction
            - action
            - args
        properties:
            type:
                const: rpc
            id:
                type: integer
            direction:
                const: request
            action:
                type: string
            args:
                type: array
      - type: object
        required:
            - type
            - id
            - direction
            - success
            - result
        properties:
            type:
                const: rpc
            id:
                type: integer
            direction:
                const: response
            success:
                type: boolean

Provided API is similar to Connection's with addition of `actions` and `call`
coroutine::

    class Connection(aio.Resource):

        def __init__(self,
                     conn: Connection,
                     actions: typing.Dict[str, aio.AsyncCallable]): ...

        @property
        def async_group(self) -> aio.Group: ...

        @property
        def local_data(self) -> json.Data: ...

        @property
        def remote_data(self) -> json.Data: ...

        def register_change_cb(self,
                               cb: typing.Callable[[], None]
                               ) -> util.RegisterCallbackHandle: ...

        def set_local_data(self, data: json.Data): ...

        async def flush_local_data(self): ...

        async def send(self, msg: json.Data): ...

        async def receive(self) -> json.Data: ...

        async def call(self,
                       action: str,
                       *args: json.Data
                       ) -> json.Data: ...


Example
-------

::

    from hat import aio
    from hat import juggler
    from hat import util

    port = util.get_unused_tcp_port()
    host = '127.0.0.1'

    server_conns = aio.Queue()
    server = await juggler.listen(host, port, server_conns.put_nowait,
                                  autoflush_delay=0)

    client_conn = await juggler.connect(f'ws://{host}:{port}/ws',
                                        autoflush_delay=0)
    server_conn = await server_conns.get()

    server_remote_data = aio.Queue()
    server_conn.register_change_cb(
        lambda: server_remote_data.put_nowait(server_conn.remote_data))

    client_conn.set_local_data(123)
    data = await server_remote_data.get()
    assert data == 123

    await server.async_close()
    await client_conn.wait_closed()
    await server_conn.wait_closed()


API
---

API reference is available as part of generated documentation:

    * `Python hat.juggler module <../../pyhat/hat/juggler.html>`_
