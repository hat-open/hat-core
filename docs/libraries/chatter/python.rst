.. _hat-chatter:

`hat.chatter` - Python chatter library
======================================

This library provides Python implementation of
:ref:`Chatter communication protocol <chatter>`.


.. _hat-chatter-connect:

Client
------

`hat.chatter.connect` coroutine creates client initiated chatter connection::

    async def connect(sbs_repo: sbs.Repository,
                      address: str,
                      *,
                      pem_file: typing.Optional[str] = None,
                      ping_timeout: float = 20,
                      queue_maxsize: int = 0
                      ) -> 'Connection': ...


.. _hat-chatter-listen:
.. _hat-chatter-Server:

Server
------

`hat.chatter.listen` coroutine creates server listening for incomming
chatter  connections::

    async def listen(sbs_repo: sbs.Repository,
                     address: str,
                     connection_cb: typing.Callable[['Connection'], None],
                     *,
                     pem_file: typing.Optional[str] = None,
                     ping_timeout: float = 20,
                     queue_maxsize: int = 0
                     ) -> 'Server':

    class Server(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

        @property
        def addresses(self) -> typing.List[str]: ...


.. _hat-chatter-Connection:

Connection
----------

Once chatter connection is established by calling `connect` or by listening
for incoming connection with `listen`, communication interface for client-side
and for server-side is the same::

    class Data(typing.NamedTuple):
        module: typing.Optional[str]
        """SBS module name"""
        type: str
        """SBS type name"""
        data: sbs.Data

    class Conversation(typing.NamedTuple):
        conn: 'Connection'
        owner: bool
        first_id: int

    class Msg(typing.NamedTuple):
        data: Data
        conv: Conversation
        first: bool
        last: bool
        token: bool

    class Connection(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

        @property
        def local_address(self) -> str: ...

        @property
        def remote_address(self) -> str: ...

        async def receive(self) -> Msg: ...

        def send(self,
                 msg_data: Data,
                 *,
                 conv: typing.Optional[Conversation] = None,
                 last: bool = True,
                 token: bool = True,
                 timeout: typing.Optional[float] = None,
                 timeout_cb: typing.Optional[typing.Callable[[Conversation],
                                                             None]] = None
                 ) -> Conversation: ...


Example
-------

::

    from hat import aio
    from hat import chatter
    from hat import sbs
    from hat import util

    sbs_repo = sbs.Repository(chatter.sbs_repo, r"""
        module Example

        Msg = Integer
    """)

    port = util.get_unused_tcp_port()
    address = f'tcp+sbs://127.0.0.1:{port}'

    server_conns = aio.Queue()
    server = await chatter.listen(sbs_repo, address, server_conns.put_nowait)

    client_conn = await chatter.connect(sbs_repo, address)
    server_conn = await server_conns.get()

    data = chatter.Data('Example', 'Msg', 123)
    client_conn.send(data)

    msg = await server_conn.receive()
    assert msg.data == data

    await server.async_close()
    await client_conn.wait_closed()
    await server_conn.wait_closed()


API
---

API reference is available as part of generated documentation:

    * `Python hat.chatter module <../../pyhat/hat/chatter/index.html>`_
