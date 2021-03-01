from hat import json
from hat.event.server.backends.lmdb import common


class Conditions:

    def __init__(self, conf: json.Data):
        self._conditions = [(common.Subscription(i['subscriptions']),
                             _create_condition(i['condition']))
                            for i in conf]

    def matches(self, event: common.Event) -> bool:
        for subscription, condition in self._conditions:
            if not subscription.matches(event.event_type):
                continue
            if not condition.matches(event):
                return False
        return True


def _create_condition(conf):
    if conf['type'] == 'all':
        return _AllCondition(conf)

    if conf['type'] == 'any':
        return _AnyCondition(conf)

    if conf['type'] == 'json':
        return _JsonCondition(conf)

    raise ValueError('unsupported condition type')


class _AllCondition:

    def __init__(self, conf):
        self._conditions = [_create_condition(i) for i in conf['conditions']]

    def matches(self, event):
        return all(condition.matches(event) for condition in self._conditions)


class _AnyCondition:

    def __init__(self, conf):
        self._conditions = [_create_condition(i) for i in conf['conditions']]

    def matches(self, event):
        return any(condition.matches(event) for condition in self._conditions)


class _JsonCondition:

    def __init__(self, conf):
        self._conf = conf

    def matches(self, event):
        if event.payload is None:
            return False
        if event.payload.type != common.EventPayloadType.JSON:
            return False

        data_path = self._conf.get('data_path', [])
        data = json.get(event.payload.data, data_path)

        if 'data_type' in self._conf:
            data_type = self._conf['data_type']

            if data_type == 'null':
                if data is not None:
                    return False

            elif data_type == 'boolean':
                if not isinstance(data, bool):
                    return False

            elif data_type == 'string':
                if not isinstance(data, str):
                    return False

            elif data_type == 'number':
                if not (isinstance(data, float) or
                        (isinstance(data, int) and
                         not isinstance(data, bool))):
                    return False

            elif data_type == 'array':
                if not isinstance(data, list):
                    return False

            elif data_type == 'object':
                if not isinstance(data, dict):
                    return False

        if 'data_value' in self._conf:
            if self._conf['data_value'] != data:
                return False

        return True
