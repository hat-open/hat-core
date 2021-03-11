import functools

import lmdb

from hat import aio
from hat.event.server.backends.lmdb import common
from hat.event.server.backends.lmdb import encoder


async def create(executor: aio.Executor,
                 env: lmdb.Environment,
                 name: str,
                 server_id: int
                 ) -> 'SystemDb':
    db = SystemDb()
    db._env = env
    db._name = name
    db._db = await executor(db._ext_open_db)

    data = await executor(db._ext_get_data)

    if not data:
        db._data = common.SystemData(server_id, None, None)

    elif data.server_id != server_id:
        raise Exception('server_id not matching')

    else:
        db._data = data

    return db


class SystemDb:

    @property
    def data(self) -> common.SystemData:
        return self._data

    def change(self,
               last_instance_id: int,
               last_timestamp: common.Timestamp):
        self._data = self._data._replace(last_instance_id=last_instance_id,
                                         last_timestamp=last_timestamp)

    def create_ext_flush(self) -> common.ExtFlushCb:
        return functools.partial(self._ext_flush, self._data)

    def _ext_open_db(self):
        return self._env.open_db(bytes(self._name, encoding='utf-8'))

    def _ext_get_data(self):
        with self._env.begin(db=self._db, buffers=True) as txn:
            data = txn.get(b'data')
            return encoder.decode_system_data(data) if data else None

    def _ext_flush(self, data, parent, now):
        with self._env.begin(db=self._db, parent=parent, write=True) as txn:
            txn.put(b'data', encoder.encode_system_data(data))
