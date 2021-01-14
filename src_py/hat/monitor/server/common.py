"""Common functionality"""

import typing

from hat import sbs

from hat.monitor.common import (ComponentInfo,
                                component_info_to_sbs,
                                component_info_from_sbs)
from hat.monitor.common import *  # NOQA


class MsgSlave(typing.NamedTuple):
    components: typing.List[ComponentInfo]


class MsgMaster(typing.NamedTuple):
    mid: int
    components: typing.List[ComponentInfo]


def msg_slave_to_sbs(msg: MsgSlave) -> sbs.Data:
    """Convert MsgSlave to SBS data"""
    return {'components': [component_info_to_sbs(info)
                           for info in msg.components]}


def msg_slave_from_sbs(data: sbs.Data) -> MsgSlave:
    """Convert SBS data to MsgSlave"""
    return MsgSlave(components=[component_info_from_sbs(info)
                                for info in data['components']])


def msg_master_to_sbs(msg: MsgMaster) -> sbs.Data:
    """Convert MsgMaster to SBS data"""
    return {'mid': msg.mid,
            'components': [component_info_to_sbs(info)
                           for info in msg.components]}


def msg_master_from_sbs(data: sbs.Data) -> MsgMaster:
    """Convert SBS data to MsgMaster"""
    return MsgMaster(mid=data['mid'],
                     components=[component_info_from_sbs(info)
                                 for info in data['components']])
