import pytest

from hat.event.server.backends.lmdb import common
import hat.event.server.backends.lmdb.conditions


def create_event(event_type, payload):
    return common.Event(event_id=common.EventId(1, 2),
                        event_type=event_type,
                        timestamp=common.now(),
                        source_timestamp=None,
                        payload=payload)


def create_json_payload(data):
    return common.EventPayload(common.EventPayloadType.JSON, data)


@pytest.mark.parametrize('conf, matching, not_matching', [
    ([{'subscriptions': [('a',)],
       'condition': {'type': 'json'}}],
     [create_event(('a',), create_json_payload(None)),
      create_event(('b',), None)],
     [create_event(('a',), None),
      create_event(('a',), common.EventPayload(common.EventPayloadType.BINARY,
                                               b''))]),

    ([{'subscriptions': [('*',)],
       'condition': {'type': 'any',
                     'conditions': [{'type': 'json',
                                     'data_value': 1},
                                    {'type': 'json',
                                     'data_value': 2}]}}],
     [create_event(('a',), create_json_payload(1)),
      create_event(('a',), create_json_payload(2))],
     [create_event(('a',), create_json_payload(3))]),

    ([{'subscriptions': [('*',)],
       'condition': {'type': 'all',
                     'conditions': [{'type': 'json',
                                     'data_path': 'x',
                                     'data_value': 1},
                                    {'type': 'json',
                                     'data_path': 'y',
                                     'data_value': 2}]}}],
     [create_event(('a',), create_json_payload({'x': 1, 'y': 2}))],
     [create_event(('a',), create_json_payload({'x': 1})),
      create_event(('a',), create_json_payload({'y': 2}))]),

    ([{'subscriptions': [('*',)],
       'condition': {'type': 'json',
                     'data_type': 'null'}}],
     [create_event(('a',), create_json_payload(None))],
     [create_event(('a',), create_json_payload(1))]),

    ([{'subscriptions': [('*',)],
       'condition': {'type': 'json',
                     'data_type': 'boolean'}}],
     [create_event(('a',), create_json_payload(True))],
     [create_event(('a',), create_json_payload(1))]),

    ([{'subscriptions': [('*',)],
       'condition': {'type': 'json',
                     'data_type': 'string'}}],
     [create_event(('a',), create_json_payload('abc'))],
     [create_event(('a',), create_json_payload(None))]),

    ([{'subscriptions': [('*',)],
       'condition': {'type': 'json',
                     'data_type': 'number'}}],
     [create_event(('a',), create_json_payload(123))],
     [create_event(('a',), create_json_payload(True))]),

    ([{'subscriptions': [('*',)],
       'condition': {'type': 'json',
                     'data_type': 'array'}}],
     [create_event(('a',), create_json_payload([1, 2, 3]))],
     [create_event(('a',), create_json_payload(None))]),

    ([{'subscriptions': [('*',)],
       'condition': {'type': 'json',
                     'data_type': 'object'}}],
     [create_event(('a',), create_json_payload({}))],
     [create_event(('a',), create_json_payload(None))]),
])
def test_conditions(conf, matching, not_matching):
    conditions = hat.event.server.backends.lmdb.conditions.Conditions(conf)

    for event in matching:
        result = conditions.matches(event)
        assert result is True

    for event in not_matching:
        result = conditions.matches(event)
        assert result is False
