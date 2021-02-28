import collections
import functools
import itertools
import typing

import lmdb

from hat import aio
from hat.event.server.backends.lmdb import common
from hat.event.server.backends.lmdb import encoder


async def create(executor: aio.Executor,
                 env: lmdb.Environment,
                 name: str,
                 subscription: common.Subscription,
                 conditions: common.Condition,
                 order_by: common.OrderBy
                 ) -> 'OrderedDb':
    db = OrderedDb()
    db._env = env
    db._name = name
    db._subscription = subscription
    db._conditions = conditions
    db._order_by = order_by
    db._changes = collections.deque()
    db._db = await executor(db._ext_open_db)
    return db


class OrderedDb:

    @property
    def has_changed(self) -> bool:
        return bool(self._changes)

    @property
    def subscription(self) -> common.Subscription:
        return self._subscription

    @property
    def order_by(self):
        return self._order_by

    def add(self, event: common.Event) -> bool:
        if not self._subscription.matches(event.event_type):
            return False

        if self._order_by == common.OrderBy.TIMESTAMP:
            key = event.timestamp, event.event_id.instance

        elif self._order_by == common.OrderBy.SOURCE_TIMESTAMP:
            if event.source_timestamp is None:
                return False
            key = event.source_timestamp, event.event_id.instance

        else:
            raise ValueError('unsupported order by')

        self._changes.append((key, event))
        return True

    async def query(self,
                    subscription: typing.Optional[common.Subscription],
                    event_ids: typing.Optional[typing.List[common.EventId]],
                    t_from: typing.Optional[common.Timestamp],
                    t_to: typing.Optional[common.Timestamp],
                    source_t_from: typing.Optional[common.Timestamp],
                    source_t_to: typing.Optional[common.Timestamp],
                    payload: typing.Optional[common.EventPayload],
                    order: common.Order,
                    unique_type: bool,
                    max_results: typing.Optional[int]
                    ) -> typing.Iterable[common.Event]:
        unique_types = set() if unique_type else None

        if order == common.Order.DESCENDING:
            events = collections.deque(self._query_changes(
                subscription, event_ids, t_from, t_to, source_t_from,
                source_t_to, payload, order, unique_types, max_results))
            yield from events

            if max_results is not None:
                max_results -= len(events)
                if max_results <= 0:
                    return

            events = await self._executor(
                self._ext_query, subscription, event_ids, t_from, t_to,
                source_t_from, source_t_to, payload, order, unique_types,
                max_results)
            yield from events

        elif order == common.Order.ASCENDING:
            events = await self._executor(
                self._ext_query, subscription, event_ids, t_from, t_to,
                source_t_from, source_t_to, payload, order, unique_types,
                max_results)
            yield from events

            if max_results is not None:
                max_results -= len(events)
                if max_results <= 0:
                    return

            yield from self._query_changes(
                subscription, event_ids, t_from, t_to, source_t_from,
                source_t_to, payload, order, unique_types, max_results)

        else:
            raise ValueError('unsupported order')

    def create_ext_flush(self) -> common.ExtFlushCb:
        changes = self._changes
        self._changes = collections.deque()
        return functools.partial(self._ext_flush, changes)

    def _query_changes(self, subscription, event_ids, t_from, t_to,
                       source_t_from, source_t_to, payload, order,
                       unique_types, max_results):
        if order == common.Order.DESCENDING:
            events = (event for _, event in reversed(self._changes))

            if (self._order_by == common.OrderBy.TIMESTAMP and
                    t_to is not None):
                events = itertools.dropwhile(
                    lambda i: t_to < i.timestamp,
                    events)

            elif (self._order_by == common.OrderBy.SOURCE_TIMESTAMP and
                    source_t_to is not None):
                events = itertools.dropwhile(
                    lambda i: source_t_to < i.source_timestamp,
                    events)

            if (self._order_by == common.OrderBy.TIMESTAMP and
                    t_from is not None):
                events = itertools.takewhile(
                    lambda i: t_from <= i.timestamp,
                    events)

            elif (self._order_by == common.OrderBy.SOURCE_TIMESTAMP and
                    source_t_from is not None):
                events = itertools.takewhile(
                    lambda i: source_t_from <= i.source_timestamp,
                    events)

        elif order == common.Order.ASCENDING:
            events = (event for _, event in self._changes)

            if (self._order_by == common.OrderBy.TIMESTAMP and
                    t_from is not None):
                events = itertools.dropwhile(
                    lambda i: i.timestamp < t_from,
                    events)

            elif (self._order_by == common.OrderBy.SOURCE_TIMESTAMP and
                    source_t_from is not None):
                events = itertools.dropwhile(
                    lambda i: i.source_timestamp < source_t_from,
                    events)

            if (self._order_by == common.OrderBy.TIMESTAMP and
                    t_to is not None):
                events = itertools.takewhile(
                    lambda i: i.timestamp <= t_to,
                    events)

            elif (self._order_by == common.OrderBy.SOURCE_TIMESTAMP and
                    source_t_to is not None):
                events = itertools.takewhile(
                    lambda i: i.source_timestamp <= source_t_to,
                    events)

        else:
            raise ValueError('unsupported order')

        for event in events:
            if max_results is not None and max_results <= 0:
                return

            if subscription and not subscription.matches(event.event_type):
                continue

            if event_ids is not None and event.event_id not in event_ids:
                continue

            if t_from is not None and event.timestamp < t_from:
                continue

            if t_to is not None and t_to < event.timestamp:
                continue

            if source_t_from is not None and (
                    event.source_timestamp is None or
                    event.source_timestamp < source_t_from):
                continue

            if source_t_to is not None and (
                    event.source_timestamp is None or
                    source_t_to < event.source_timestamp):
                continue

            if payload is not None and event.payload != payload:
                continue

            if unique_types is not None:
                if event.event_type in unique_types:
                    continue
                unique_types.add(event.event_type)

            if max_results is not None:
                max_results -= 1

            yield event

    def _ext_open_db(self):
        return self._env.open_db(bytes(self._name, encoding='utf-8'))

    def _ext_query(self, subscription, event_ids, t_from, t_to,
                   source_t_from, source_t_to, payload, order,
                   unique_types, max_results):
        raise NotImplementedError()

    def _ext_flush(self, changes, parent):
        with self._env.begin(db=self._db, parent=parent, write=True) as txn:
            for key, value in changes:
                # TODO: maybe call put with append=True
                txn.put(encoder.encode_timestamp_id(key),
                        encoder.encode_event(value))
