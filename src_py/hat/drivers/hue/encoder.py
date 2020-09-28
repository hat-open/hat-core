import datetime

from hat.drivers.hue import common


def state_from_json(device_type, state):
    if device_type == common.DeviceType.LIGHT:
        return _light_state_from_json(state)
    if device_type == common.DeviceType.SENSOR:
        return _sensor_state_from_json(state)
    raise ValueError('invalid device type')


def state_to_json(state):
    if isinstance(state, common.LightState):
        return _light_state_to_json(state)
    if isinstance(state, common.SensorState):
        return _sensor_state_to_json(state)
    raise ValueError('invalid state type')


def device_from_json(device_id, device):
    state = state_from_json(device_id.type, device['state'])
    return common.Device(id=device_id,
                         subtype=device['type'],
                         name=device['name'],
                         model_id=device['modelid'],
                         manufacturer_name=device['manufacturername'],
                         sw_version=device['swversion'],
                         unique_id=device.get('uniqueid'),
                         state=state)


def _light_state_from_json(state):
    alert = common.LightAlert(state['alert']) if 'alert' in state else None
    effect = common.LightEffect(state['effect']) if 'effect' in state else None
    return common.LightState(
        on=state.get('on'),
        bri=state.get('bri'),
        alert=alert,
        reachable=state.get('reachable'),
        hue=state.get('hue'),
        sat=state.get('sat'),
        effect=effect)


def _light_state_to_json(state):
    data = {}
    if state.on is not None:
        data['on'] = state.on
    if state.bri is not None:
        data['bri'] = state.bri
    if state.alert is not None:
        data['alert'] = state.alert.value
    if state.reachable is not None:
        data['reachable'] = state.reachable
    if state.hue is not None:
        data['hue'] = state.hue
    if state.sat is not None:
        data['sat'] = state.sat
    if state.effect is not None:
        data['effect'] = state.effect.value
    return data


def _sensor_state_from_json(state):
    last_updated = _datetime_from_json(state['lastupdated'])
    return common.SensorState(last_updated=last_updated)


def _sensor_state_to_json(state):
    return {}


def _datetime_from_json(t):
    if not t or t == 'none':
        return
    dt = datetime.strptime(t, "%Y-%m-%dT%H:%M:%S")
    return dt.replace(tzinfo=datetime.timezone.utc)
