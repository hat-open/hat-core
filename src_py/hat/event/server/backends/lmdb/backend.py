from pathlib import Path
import asyncio
import collections
import logging
import typing

import lmdb

from hat import aio
from hat import json
from hat.event.server.backends.lmdb import common
from hat.event.server.backends.lmdb.conditions import Conditions
import hat.event.server.backends.lmdb.latestdb
import hat.event.server.backends.lmdb.ordereddb
import hat.event.server.backends.lmdb.systemdb


mlog = logging.getLogger(__name__)


async def create(conf: json.Data
                 ) -> 'LmdbBackend':
    backend = LmdbBackend()
    backend._sync_period = conf['sync_period']
    backend._executor = aio.create_executor(1)

    backend._conditions = Conditions(conf['conditions'])

    backend._env = await backend._executor(
        _ext_create_env, Path(conf['db_path']), conf['max_db_size'],
        2 + 2 * len(conf['ordered']))

    backend._sys_db = await hat.event.server.backends.lmdb.systemdb.create(
        backend._executor, backend._env, 'system', conf['server_id'])

    subscription = common.Subscription(
        tuple(i) for i in conf['latest']['subscriptions'])
    backend._latest_db = await hat.event.server.backends.lmdb.latestdb.create(
        backend._executor, backend._env, 'latest', subscription,
        backend._conditions)

    backend._ordered_dbs = collections.deque()
    for i, i_conf in enumerate(conf['ordered']):
        order_by = common.OrderBy[i_conf['order_by']]
        subscription = common.Subscription(tuple(et)
                                           for et in i_conf['subscriptions'])
        limit = i_conf.get('limit')
        name = f'ordered_{i}'
        ordered_dbs = await hat.event.server.backends.lmdb.ordereddb.create(
            backend._executor, backend._env, name, subscription,
            backend._conditions, order_by, limit)
        backend._ordered_dbs.append(ordered_dbs)

    backend._async_group = aio.Group()
    backend._async_group.spawn(backend._write_loop)

    return backend


class LmdbBackend(common.Backend):

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    async def get_last_event_id(self,
                                server_id: int
                                ) -> common.EventId:
        if server_id != self._sys_db.data.server_id:
            return common.EventId(server=server_id,
                                  instance=0)

        instance_id = self._sys_db.data.last_instance_id or 0
        return common.EventId(server=server_id,
                              instance=instance_id)

    async def register(self,
                       events: typing.List[common.Event]
                       ) -> typing.List[common.Event]:
        sorted_events = sorted(events, key=lambda x: x.event_id)
        for event in sorted_events:
            server_id = self._sys_db.data.server_id
            if server_id != event.event_id.server:
                mlog.warning("event registration skipped: invalid server id")
                continue

            last_instance_id = self._sys_db.data.last_instance_id
            if (last_instance_id is not None and
                    last_instance_id >= event.event_id.instance):
                mlog.warning("event registration skipped: invalid instance id")
                continue

            last_timestamp = self._sys_db.data.last_timestamp
            if (last_timestamp is not None and
                    last_timestamp > event.timestamp):
                mlog.warning("event registration skipped: invalid timestamp")
                continue

            if not self._conditions.matches(event):
                mlog.warning("event registration skipped: invalid conditions")
                continue

            registered = False

            if self._latest_db.add(event):
                registered = True

            for db in self._ordered_dbs:
                if db.add(event):
                    registered = True

            if registered:
                self._sys_db.change(event.event_id.instance, event.timestamp)

        return events

    async def query(self,
                    data: common.QueryData
                    ) -> typing.List[common.Event]:
        if (data.event_ids is None and
                data.t_to is None and
                data.source_t_from is None and
                data.source_t_to is None and
                data.payload is None and
                data.order == common.Order.DESCENDING and
                data.order_by == common.OrderBy.TIMESTAMP and
                data.unique_type):
            events = self._latest_db.query(event_types=data.event_types)

            if data.t_from is not None:
                events = (event for event in events
                          if data.t_from <= event.timestamp)

            events = sorted(events,
                            key=lambda i: (i.timestamp, i.event_id),
                            reverse=True)

            if data.max_results is not None:
                events = events[:data.max_results]

            return events

        subscription = (common.Subscription(data.event_types)
                        if data.event_types is not None else None)

        for db in self._ordered_dbs:
            if db.order_by != data.order_by:
                continue
            if subscription and subscription.isdisjoint(db.subscription):
                continue

            events = await db.query(subscription=subscription,
                                    event_ids=data.event_ids,
                                    t_from=data.t_from,
                                    t_to=data.t_to,
                                    source_t_from=data.source_t_from,
                                    source_t_to=data.source_t_to,
                                    payload=data.payload,
                                    order=data.order,
                                    unique_type=data.unique_type,
                                    max_results=data.max_results)
            return list(events)

        return []

    async def _write_loop(self):
        try:
            while True:
                await asyncio.sleep(self._sync_period)
                await aio.uncancellable(self._flush_env())

        except Exception as e:
            mlog.error('backend write error: %s', e, exc_info=e)

        finally:
            self.close()
            await aio.uncancellable(self._close_env())

    async def _flush_env(self):
        dbs = [self._sys_db, self._latest_db, *self._ordered_dbs]
        ext_db_flush_fns = [db.create_ext_flush() for db in dbs]
        await self._executor(_ext_flush, self._env, ext_db_flush_fns)

    async def _close_env(self):
        await self._flush_env()
        await self._executor(self._env.close)


def _ext_create_env(path, max_size, max_dbs):
    return lmdb.Environment(str(path), map_size=max_size, subdir=False,
                            max_dbs=max_dbs)


def _ext_flush(env, db_flush_fns):
    now = common.now()
    with env.begin(write=True) as txn:
        for db_flush_fn in db_flush_fns:
            db_flush_fn(txn, now)
