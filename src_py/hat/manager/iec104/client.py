from hat import aio
from hat import juggler


class Client(aio.Resource):

    def __init__(self, conn):
        self._conn = juggler.RpcConnection(conn, {})

    @property
    def async_group(self):
        return self._conn.async_group
