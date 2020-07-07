import datetime

import pytest

from hat.util import json
from hat.syslog.common import (Msg, Facility, Severity,
                               msg_to_str, msg_from_str,
                               msg_to_json, msg_from_json)


valid_msgs = [
    Msg(facility=Facility.KERNEL,
        severity=Severity.EMERGENCY,
        version=1,
        timestamp=None,
        hostname=None,
        app_name=None,
        procid=None,
        msgid=None,
        data=None,
        msg=None),
    Msg(facility=Facility.USER,
        severity=Severity.DEBUG,
        version=1,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc).timestamp(),
        hostname='abc1',
        app_name='abc2',
        procid='abc3',
        msgid='abc4',
        data=json.encode({'xyz@1': {'a': 'b',
                                    'd': 'e',
                                    'f': '"]\\\\',
                                    'g': ''},
                          'abc@1': {}}),
        msg='abcabcabcabc')
]

invalid_msgs = [
    Msg(facility=None,
        severity=None,
        version=None,
        timestamp=None,
        hostname=None,
        app_name=None,
        procid=None,
        msgid=None,
        data=None,
        msg=None)
]


@pytest.mark.parametrize("msg", valid_msgs)
def test_valid_msg_str_serialization(msg):
    msg_str = msg_to_str(msg)
    assert msg == msg_from_str(msg_str)


@pytest.mark.parametrize("msg", valid_msgs)
def test_valid_msg_json_serialization(msg):
    msg_json = msg_to_json(msg)
    assert msg == msg_from_json(msg_json)


@pytest.mark.parametrize("msg", invalid_msgs)
def test_invalid_msg_str_serialization(msg):
    with pytest.raises(Exception):
        msg_str = msg_to_str(msg)
        assert msg == msg_from_str(msg_str)


@pytest.mark.parametrize("msg", invalid_msgs)
def test_invalid_msg_json_serialization(msg):
    with pytest.raises(Exception):
        msg_json = msg_to_json(msg)
        assert msg == msg_from_json(msg_json)
