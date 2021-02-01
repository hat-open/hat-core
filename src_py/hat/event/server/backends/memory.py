"""Simple memory backend

All registered events are stored in single unsorted continuous event list.

"""

import collections
import typing

from hat import aio
from hat import json
from hat.event.server import common


json_schema_id = None
json_schema_repo = None


async def create(conf: json.Data) -> 'MemoryBackend':
    backend = MemoryBackend()
    backend._async_group = aio.Group()
    backend._events = collections.deque()
    return backend


class MemoryBackend(common.Backend):

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    async def get_last_event_id(self,
                                server_id: int
                                ) -> common.EventId:
        event_ids = (e.event_id for e in self._events
                     if e.server == server_id)
        key = lambda event_id: event_id.instance  # NOQA
        default = common.EventId(server=server_id, instance=0)
        return max(event_ids, key=key, default=default)

    async def register(self,
                       events: typing.List[common.Event]
                       ) -> typing.List[typing.Optional[common.Event]]:
        self._events.extend(events)
        return events

    async def query(self,
                    data: common.QueryData
                    ) -> typing.List[common.Event]:
        events = self._events

        if data.event_ids is not None:
            events = _filter_events_ids(events, data.event_ids)

        if data.event_types is not None:
            events = _filter_event_types(events, data.event_types)

        if data.t_from is not None:
            events = _filter_t_from(events, data.t_from)

        if data.t_to is not None:
            events = _filter_t_to(events, data.t_to)

        if data.source_t_from is not None:
            events = _filter_source_t_from(events, data.source_t_from)

        if data.source_t_to is not None:
            events = _filter_source_t_to(events, data.source_t_to)

        if data.payload is not None:
            events = _filter_payload(events, data.payload)

        if data.order_by == common.OrderBy.TIMESTAMP:
            sort_key = lambda event: event.timestamp  # NOQA
        elif data.order_by == common.OrderBy.SOURCE_TIMESTAMP:
            sort_key = lambda event: event.source_timestamp  # NOQA
        else:
            raise ValueError('invalid order by')

        if data.order == common.Order.ASCENDING:
            sort_reverse = False
        elif data.order == common.Order.DESCENDING:
            sort_reverse = True
        else:
            raise ValueError('invalid order by')

        events = sorted(events, key=sort_key, reverse=sort_reverse)

        if data.unique_type:
            events = _filter_unique_type(events)

        if data.max_results is not None:
            events = _filter_max_results(events, data.max_results)

        return list(events)


def _filter_events_ids(events, event_ids):
    for event in event_ids:
        if event.event_id in event_ids:
            yield event


def _filter_event_types(events, event_types):
    subscription = common.Subscription(event_types)
    for event in events:
        if subscription.matches(event.event_type):
            yield event


def _filter_t_from(events, t_from):
    for event in events:
        if event.timestamp >= t_from:
            yield event


def _filter_t_to(events, t_to):
    for event in events:
        if event.timestamp <= t_to:
            yield event


def _filter_source_t_from(events, source_t_from):
    for event in events:
        if event.source_timestamp >= source_t_from:
            yield event


def _filter_source_t_to(events, source_t_to):
    for event in events:
        if event.source_timestamp <= source_t_to:
            yield event


def _filter_payload(events, payload):
    for event in events:
        if event.payload == payload:
            yield event


def _filter_unique_type(events):
    event_types = set()
    for event in events:
        event_type = tuple(event.event_type)
        if event_type in event_types:
            continue
        event_types.add(event_type)
        yield event


def _filter_max_results(events, max_results):
    for i, event in enumerate(events):
        if i >= max_results:
            break
        yield events
