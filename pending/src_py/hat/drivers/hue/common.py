import datetime
import enum
import typing


class LightAlert(enum.Enum):
    NONE = 'none'
    SELECT = 'select'
    LSELECT = 'lselect'


class LightEffect(enum.Enum):
    NONE = 'none'
    COLOR_LOOP = 'colorloop'


class DeviceType(enum.Enum):
    LIGHT = 'lights'
    SENSOR = 'sensors'


class DeviceId(typing.NamedTuple):
    type: DeviceType
    label: str


class LightState(typing.NamedTuple):
    """Light state

    Attributes:
        on: on/off state
        bri: brightness between 1 (min) and 254 (max)
        alert: light alert state
        reachable: is device reachable
        hue: hue between 0 and 65535
        sat: saturnation between 0 (white) and 254 (colored)
        effect: light effect

    """
    on: typing.Optional[bool] = None
    bri: typing.Optional[int] = None
    alert: typing.Optional[LightAlert] = None
    reachable: typing.Optional[bool] = None
    hue: typing.Optional[int] = None
    sat: typing.Optional[int] = None
    effect: typing.Optional[LightEffect] = None


class SensorState(typing.NamedTuple):
    """Sensor state

    Attributes:
        last_updated: last updated time

    """
    last_updated: typing.Optional[datetime.datetime] = None


DeviceState = typing.Union[LightState, SensorState]


class Device(typing.NamedTuple):
    id: DeviceId
    subtype: str
    name: str
    model_id: str
    manufacturer_name: str
    sw_version: str
    unique_id: typing.Optional[str]
    state: DeviceState
