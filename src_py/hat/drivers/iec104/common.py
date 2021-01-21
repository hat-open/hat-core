"""IEC 60870-5-104 data structures"""

import datetime
import enum
import time
import typing


class Data(typing.NamedTuple):
    value: 'DataValue'
    quality: 'Quality'
    """quality (optional in case of NormalizedValue without quality and BinaryCounterValue)"""  # NOQA
    time: typing.Optional['Time']
    asdu_address: int
    io_address: int
    cause: 'Cause'
    is_test: bool


class Command(typing.NamedTuple):
    action: 'Action'
    value: 'CommandValue'
    asdu_address: int
    io_address: int
    time: typing.Optional['Time']
    qualifier: int


class SingleValue(enum.Enum):
    OFF = 0
    ON = 1


class DoubleValue(enum.Enum):
    """DoubleDataValue

    `FAULT` stands for value 3, defined in the protocol as *INDETERMINATE*.
    This is in order to make it more distinguishable from ``INTERMEDIATE``.

    """
    INTERMEDIATE = 0
    OFF = 1
    ON = 2
    FAULT = 3


class RegulatingValue(enum.Enum):
    LOWER = 1
    HIGHER = 2


class StepPositionValue(typing.NamedTuple):
    value: int
    """value in range [-64, 63]"""
    transient: bool


class BitstringValue(typing.NamedTuple):
    value: bytes
    """bitstring encoded as 4 bytes"""


class NormalizedValue(typing.NamedTuple):
    value: float
    """value in range [-1.0, 1.0]"""


class ScaledValue(typing.NamedTuple):
    value: int
    """value in range [-2^15, 2^15-1]"""


class FloatingValue(typing.NamedTuple):
    value: float


class BinaryCounterValue(typing.NamedTuple):
    value: int
    """value in range [-2^31, 2^31-1]"""
    sequence: int
    overflow: bool
    adjusted: bool
    invalid: bool


DataValue = typing.Union[SingleValue,
                         DoubleValue,
                         StepPositionValue,
                         BitstringValue,
                         NormalizedValue,
                         ScaledValue,
                         FloatingValue,
                         BinaryCounterValue]


CommandValue = typing.Union[SingleValue,
                            DoubleValue,
                            RegulatingValue,
                            NormalizedValue,
                            ScaledValue,
                            FloatingValue]


class Quality(typing.NamedTuple):
    invalid: bool
    not_topical: bool
    substituted: bool
    blocked: bool
    overflow: bool
    """owerflow flag (for SingleValue and DoubleValue always False)"""


class Time(typing.NamedTuple):
    milliseconds: int
    invalid: bool
    minutes: int
    summer_time: bool
    hours: int
    day_of_week: int
    day_of_month: int
    months: int
    years: int


class Cause(enum.Enum):
    UNDEFINED = 0
    PERIODIC = 1
    BACKGROUND_SCAN = 2
    SPONTANEOUS = 3
    INITIALIZED = 4
    REQUEST = 5
    ACTIVATION = 6
    ACTIVATION_CONFIRMATION = 7
    DEACTIVATION = 8
    DEACTIVATION_CONFIRMATION = 9
    ACTIVATION_TERMINATION = 10
    REMOTE_COMMAND = 11
    LOCAL_COMMAND = 12
    FILE_TRANSFER = 13
    INTERROGATED_STATION = 20
    INTERROGATED_GROUP01 = 21
    INTERROGATED_GROUP02 = 22
    INTERROGATED_GROUP03 = 23
    INTERROGATED_GROUP04 = 24
    INTERROGATED_GROUP05 = 25
    INTERROGATED_GROUP06 = 26
    INTERROGATED_GROUP07 = 27
    INTERROGATED_GROUP08 = 28
    INTERROGATED_GROUP09 = 29
    INTERROGATED_GROUP10 = 30
    INTERROGATED_GROUP11 = 31
    INTERROGATED_GROUP12 = 32
    INTERROGATED_GROUP13 = 33
    INTERROGATED_GROUP14 = 34
    INTERROGATED_GROUP15 = 35
    INTERROGATED_GROUP16 = 36
    INTERROGATED_COUNTER = 37
    INTERROGATED_COUNTER01 = 38
    INTERROGATED_COUNTER02 = 39
    INTERROGATED_COUNTER03 = 40
    INTERROGATED_COUNTER04 = 41
    UNKNOWN_TYPE = 44
    UNKNOWN_CAUSE = 45
    UNKNOWN_ASDU_ADDRESS = 46
    UNKNOWN_IO_ADDRESS = 47


class Action(enum.Enum):
    EXECUTE = 'execute'
    SELECT = 'select'
    CANCEL = 'cancel'


class FreezeCode(enum.Enum):
    READ = 0
    FREEZE = 1
    FREEZE_AND_RESET = 2
    RESET = 3


def time_from_datetime(dt, invalid=False):
    """Create Time from datetime.datetime

    Args:
        dt (datetime.datetime): datetime
        invalid (bool): invalid flag value

    Returns:
        Time

    """
    #  rounding microseconds to the nearest millisecond
    dt_rounded = (
        dt.replace(microsecond=0) +
        datetime.timedelta(milliseconds=round(dt.microsecond / 1000)))
    local_time = time.localtime(
        dt_rounded.replace(tzinfo=datetime.timezone.utc).timestamp())
    return Time(
        milliseconds=(local_time.tm_sec * 1000 +
                      dt_rounded.microsecond // 1000),
        invalid=invalid,
        minutes=local_time.tm_min,
        summer_time=bool(local_time.tm_isdst),
        hours=local_time.tm_hour,
        day_of_week=local_time.tm_wday + 1,
        day_of_month=local_time.tm_mday,
        months=local_time.tm_mon,
        years=local_time.tm_year % 100)


def time_to_datetime(t):
    """Convert Time to datetime.datetime

    Args:
        t (Time): time

    Returns:
        datetime.datetime

    """
    local_dt = datetime.datetime(
        year=2000 + t.years if t.years < 70 else 1900 + t.years,
        month=t.months,
        day=t.day_of_month,
        hour=t.hours,
        minute=t.minutes,
        second=int(t.milliseconds / 1000),
        microsecond=(t.milliseconds % 1000) * 1000,
        fold=not t.summer_time)
    return local_dt.astimezone(tz=datetime.timezone.utc)
