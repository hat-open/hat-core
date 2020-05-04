import functools

from hat.util import aio
import hat.event.common
import hat.event.server.common


async def create(conf):
    backend = MemoryBackend()
    backend._async_group = aio.Group()
    backend._mappings = {}
    backend._events = []
    backend._query_data_queue = aio.Queue()
    return backend


class MemoryBackend(hat.event.server.common.Backend):

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self):
        await self._async_group.async_close()

    async def get_event_type_id_mappings(self):
        return self._mappings

    async def add_event_type_id_mappings(self, mappings):
        self._mappings.update(mappings)

    async def get_last_event_id(self, server_id):
        return max(filter(lambda i: i.server == server_id,
                          (e.event_id for e in self._events)),
                   key=lambda i: i.instance,
                   default=hat.event.common.EventId(server=server_id,
                                                    instance=0))

    async def register(self, events):
        self._events += events
        return events

    async def query(self, data):

        def _get_filter(query_opt):
            return {
                'event_ids': _event_ids,
                'event_type_ids': _event_type_ids,
                't_from': _t_from,
                't_to': _t_to,
                'source_t_from': _source_t_from,
                'source_t_to': _source_t_to,
                'payload': _payload,
                'order': functools.partial(_order, order_by=data.order_by),
                'order_by': lambda events, _: list(events),
                'unique_type': _unique_type,
                'max_results': _max_results,
                }[query_opt]

        self._query_data_queue.put_nowait(data)
        ret = self._events
        for f_name, f_value in data._asdict().items():
            if f_value is None:
                continue
            ret = _get_filter(f_name)(ret, f_value)
        return ret


def _event_ids(events, event_ids):
    return filter(lambda i: i.event_id in event_ids, events)


def _event_type_ids(events, event_type_ids):
    return filter(lambda i: i.event_type_id in event_type_ids, events)


def _t_from(events, t_from):
    return filter(lambda i: i.timestamp >= t_from, events)


def _t_to(events, t_to):
    return filter(lambda i: i.timestamp <= t_to, events)


def _source_t_from(events, t_from):
    return filter(lambda i: i.source_timestamp >= t_from, events)


def _source_t_to(events, t_to):
    return filter(lambda i: i.source_timestamp <= t_to, events)


def _payload(events, payload):
    return filter(lambda i: i.payload == payload, events)


def _unique_type(events, unique_type):
    if not unique_type:
        return list(events)
    type_ids = set()
    ret = []
    for e in events:
        if e.event_type_id in type_ids:
            continue
        ret.append(e)
        type_ids.add(e.event_type_id)
    return ret


def _max_results(events, max_results):
    return events[:max_results]


def _order(events, order, order_by):
    reversed = hat.event.common.Order.DESCENDING == order
    key = {hat.event.common.OrderBy.TIMESTAMP:
           lambda i: (i.timestamp, i.source_timestamp),
           hat.event.common.OrderBy.SOURCE_TIMESTAMP:
               lambda i: (i.source_timestamp, i.timestamp)}[order_by]
    return sorted(events, key=key, reverse=reversed)
