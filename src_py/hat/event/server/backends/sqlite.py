"""Sqlite backend

Attributes:
    json_schema_id (str): JSON schema id

"""

from pathlib import Path
import asyncio
import contextlib

from hat import aio
from hat import json
from hat import sqlite3
from hat.event.server import common
from hat.event.server import registry


json_schema_id = "hat://event/backends/sqlite.yaml#"
json_schema_repo = common.json_schema_repo

_db_structure = """
    BEGIN;
    CREATE TABLE IF NOT EXISTS mappings (
        event_type_id INTEGER PRIMARY KEY NOT NULL,
        event_type TEXT NOT NULL UNIQUE);
    CREATE TABLE IF NOT EXISTS events (
        server_id INTEGER NOT NULL,
        instance_id INTEGER NOT NULL,
        event_type_id INTEGER NOT NULL,
        timestamp BLOB NOT NULL,
        source_timestamp BLOB,
        payload BLOB,
        PRIMARY KEY (server_id, instance_id));
    CREATE INDEX IF NOT EXISTS events_ts_idx ON events (
        timestamp DESC);
    CREATE INDEX IF NOT EXISTS events_source_ts_idx ON events (
        source_timestamp DESC);
    CREATE INDEX IF NOT EXISTS events_evt_type_ts_idx ON events (
        event_type_id, timestamp DESC);
    CREATE INDEX IF NOT EXISTS events_evt_type_source_ts_idx ON events (
        event_type_id, source_timestamp DESC);
    CREATE INDEX IF NOT EXISTS events_payload_idx ON events(payload);
    COMMIT;
"""


async def create(conf):
    """Create SqliteBackend

    Args:
        conf (json.Data):
            configuration defined by ``hat://event/backends/sqlite.yaml#``

    Returns:
        SqliteBackend

    """
    backend = SqliteBackend()
    backend._async_group = aio.Group()
    backend._last_instance_ids = {}
    db_path = Path(conf['db_path'])
    backend._conn = await _create_connection(db_path)
    await backend._conn.execute_script(_db_structure)
    backend._query_pool = await _create_connection_pool(
        db_path, conf['query_pool_size'])
    backend._event_type_registry = await registry.create_event_type_registry(
        backend)
    backend._async_group.spawn(aio.call_on_cancel,
                               backend._query_pool.async_close)
    backend._async_group.spawn(aio.call_on_cancel,
                               backend._conn.async_close)
    return backend


class SqliteBackend(common.Backend, registry.EventTypeRegistryStorage):

    @property
    def async_group(self):
        return self._async_group

    async def get_event_type_mappings(self):
        """See :meth:`common.EventTypeRegistryStorage.get_event_type_mappings`"""  # NOQA
        result = await self._conn.execute("SELECT * FROM mappings")
        return {row[0]: json.decode(row[1]) for row in result}

    async def add_event_type_mappings(self, mappings):
        """See :meth:`common.EventTypeRegistryStorage.add_event_type_mappings`"""  # NOQA
        labels = [
            'event_type_id',
            'event_type']
        sql = "INSERT INTO mappings ({columns}) VALUES({values})".format(
            columns=', '.join(labels),
            values=', '.join(f':{label}' for label in labels))
        params = [{
            'event_type_id': event_type_id,
            'event_type': json.encode(event_type)
        } for event_type_id, event_type in mappings.items()]

        async with self._conn.transaction():
            await self._conn.execute_many(sql, params)

    async def get_last_event_id(self, server_id):
        """See :meth:`common.Backend.get_last_event_id`"""
        if server_id not in self._last_instance_ids:
            result = await self._conn.execute(
                "SELECT max(instance_id) FROM events "
                "WHERE server_id = :server_id",
                {'server_id': server_id})
            instance_id = result[0][0] if result[0][0] is not None else 0
            self._last_instance_ids[server_id] = instance_id
        return common.EventId(server=server_id,
                              instance=self._last_instance_ids[server_id])

    async def register(self, events):
        """See :meth:`common.Backend.register`"""
        labels = [
            'server_id',
            'instance_id',
            'event_type_id',
            'timestamp',
            'source_timestamp',
            'payload']
        sql = "INSERT INTO events ({columns}) VALUES({values})".format(
            columns=', '.join(labels),
            values=', '.join(f':{label}' for label in labels))
        event_type_ids = await self._event_type_registry.get_identifiers(
            event.event_type for event in events)
        params = [{
            'server_id': event.event_id.server,
            'instance_id': event.event_id.instance,
            'event_type_id': event_type_id,
            'timestamp': common.timestamp_to_bytes(event.timestamp),
            'source_timestamp':
                common.timestamp_to_bytes(event.source_timestamp)
                if event.source_timestamp else None,
            'payload': (self._encode_payload(event.payload)
                        if event.payload else None)
        } for event, event_type_id in zip(events, event_type_ids)]

        async with self._conn.transaction():
            await self._conn.execute_many(sql, params)
        _update_last_instance_ids(self._last_instance_ids, events)
        return events

    async def query(self, data):
        """See :meth:`common.Backend.query`"""
        conditions = []
        event_type_id_condition = None
        params = {}

        if data.max_results is not None and data.max_results <= 0:
            return []
        if data.event_ids is not None:
            if not data.event_ids:
                return []
            subconditions = []
            for i, event_id in enumerate(data.event_ids):
                server_label = f'server_id_{i}'
                instance_label = f'instance_id_{i}'
                params[server_label] = event_id.server
                params[instance_label] = event_id.instance
                subconditions.append(f"(server_id = :{server_label} AND "
                                     f"instance_id = :{instance_label})")
            conditions.append(f"({' OR '.join(subconditions)})")
        if data.event_types is not None:
            event_type_ids = self._event_type_registry.query_identifiers(
                data.event_types)
            if not event_type_ids:
                return []
            labels = []
            for i, event_type_id in enumerate(event_type_ids):
                label = f'event_type_id_{i}'
                params[label] = event_type_id
                labels.append(label)
            event_type_id_condition = (
                "event_type_id IN (" +
                ', '.join(f":{label}" for label in labels) + ")")
        if data.t_from is not None:
            conditions.append("timestamp >= :t_from")
            params['t_from'] = common.timestamp_to_bytes(data.t_from)
        if data.t_to is not None:
            conditions.append("timestamp <= :t_to")
            params['t_to'] = common.timestamp_to_bytes(data.t_to)
        if data.source_t_from is not None:
            conditions.append("source_timestamp >= :source_t_from")
            params['source_t_from'] = common.timestamp_to_bytes(
                data.source_t_from)
        if data.source_t_to is not None:
            conditions.append("source_timestamp <= :source_t_to")
            params['source_t_to'] = common.timestamp_to_bytes(data.source_t_to)
        if data.payload is not None:
            conditions.append("payload = :payload")
            params['payload'] = self._encode_payload(data.payload)

        order_cols = {
            common.OrderBy.TIMESTAMP: ('timestamp', 'source_timestamp'),
            common.OrderBy.SOURCE_TIMESTAMP: ('source_timestamp', 'timestamp')
        }[data.order_by]
        order_by = {common.Order.ASCENDING: " ASC NULLS LAST",
                    common.Order.DESCENDING: " DESC NULLS LAST"}
        ordering_term = (f"{order_cols[0]} {order_by[data.order]}, "
                         f"{order_cols[1]} DESC NULLS LAST")

        if data.unique_type:
            key_columns = ['server_id', 'instance_id']
            # uglier, but much, much faster than PARTITION BY if
            # len(mappings) << len(events) because with this query
            # proper indexes are used
            sql = (
                "SELECT e.* FROM events AS e JOIN (SELECT " +
                ", ".join(f"(SELECT {column} FROM events " +
                          " WHERE event_type_id = m.event_type_id" +
                          (" AND " + " AND ".join(conditions)
                           if conditions else "") +
                          f" ORDER BY {ordering_term} LIMIT 1) AS t_{column}"
                          for column in key_columns) +
                " FROM mappings m" +
                (f" WHERE {event_type_id_condition}"
                 if event_type_id_condition else "") +
                ") ON " + " AND ".join(f"e.{column} = t_{column}"
                                       for column in key_columns) +
                f" ORDER BY {ordering_term}" +
                (f" LIMIT {data.max_results}" if data.max_results else ""))
        else:
            if event_type_id_condition:
                conditions.append(event_type_id_condition)
            sql = (
                "SELECT * FROM events" +
                (" WHERE " + " AND ".join(conditions) if conditions else "") +
                f" ORDER BY {ordering_term}" +
                (f" LIMIT {data.max_results}" if data.max_results else ""))

        async with self._query_pool.acquire() as conn:
            result = await conn.execute(sql, params)

        return [common.Event(
            event_id=common.EventId(server=row[0], instance=row[1]),
            event_type=self._event_type_registry.get_event_type(row[2]),
            timestamp=common.timestamp_from_bytes(row[3]),
            source_timestamp=(common.timestamp_from_bytes(row[4])
                              if row[4] is not None else None),
            payload=(self._decode_payload(row[5])
                     if row[5] is not None else None)
        ) for row in result]

    def _encode_payload(self, payload):
        return common.sbs_repo.encode('HatEvent', 'EventPayload',
                                      common.event_payload_to_sbs(payload))

    def _decode_payload(self, payload):
        return common.event_payload_from_sbs(common.sbs_repo.decode(
            'HatEvent', 'EventPayload', payload))


def _update_last_instance_ids(last_ids, events):
    for event in events:
        instance_id = last_ids.get(event.event_id.server, None)
        last_ids[event.event_id.server] = (
            max(instance_id, event.event_id.instance)
            if instance_id is not None else event.event_id.instance)


async def _create_connection_pool(db_path, pool_size=5):
    pool = _ConnectionPool()
    conn_futures = (_create_connection(db_path) for _ in range(pool_size))
    pool._conns = await asyncio.gather(*conn_futures)
    pool._queue = aio.Queue()
    for conn in pool._conns:
        pool._queue.put_nowait(conn)
    return pool


class _ConnectionPool:

    async def async_close(self):
        self._queue.close()
        close_futures = (i.async_close() for i in self._conns)
        await asyncio.gather(*close_futures)

    @contextlib.asynccontextmanager
    async def acquire(self):
        conn = await self._queue.get()
        try:
            yield conn
        finally:
            self.release(conn)

    def release(self, conn):
        self._queue.put_nowait(conn)


async def _create_connection(db_path):
    conn = _Connection()
    conn._executor = aio.create_executor(1)
    conn._db = await conn._executor(_ext_connect, db_path)
    return conn


class _Connection:

    async def async_close(self):
        await self._executor(self._db.close)

    @contextlib.asynccontextmanager
    async def transaction(self):
        await self.execute('BEGIN')
        try:
            yield
            await self.execute('COMMIT')
        except Exception:
            await self.execute('ROLLBACK')

    async def execute(self, sql, parameters=()):
        return await self._executor(_ext_execute, self._db, sql, parameters)

    async def execute_many(self, sql, parameters=[]):
        return await self._executor(_ext_execute_many, self._db,
                                    sql, parameters)

    async def execute_script(self, sql):
        return await self._executor(_ext_execute_script, self._db, sql)


def _ext_connect(db_path):
    db_path.parent.mkdir(exist_ok=True)
    db = sqlite3.connect('file:{}?nolock=1'.format(str(db_path)), uri=True,
                         isolation_level=None,
                         detect_types=sqlite3.PARSE_DECLTYPES)
    return db


def _ext_execute(db, sql, parameters):
    return db.execute(sql, parameters).fetchall()


def _ext_execute_many(db, sql, parameters):
    return db.executemany(sql, parameters).fetchall()


def _ext_execute_script(db, sql):
    return db.executescript(sql).fetchall()
