"""Common functionality shared between clients and monitor server"""

from hat import chatter
from hat import sbs
from hat import util


ComponentInfo = util.namedtuple(
    'ComponentInfo',
    ['cid', "int: component id"],
    ['mid', "int: monitor id"],
    ['name', "str: component name"],
    ['group', "str: component group"],
    ['address', "Optional[str]: address"],
    ['rank', "int: component rank"],
    ['blessing', "Optional[int]: blessing token"],
    ['ready', "Optional[int]: ready token"])


def create_sbs_repo(schemas_sbs_path=None):
    """Create monitor SBS repository

    Created SBS repository contains chatter message definitions with monitor
    message data definitions.

    Args:
        schemas_sbs_path (Optional[pathlib.Path]): alternative schemas_sbs path

    Returns:
        hat.sbs.Repository

    """
    schemas_sbs_path = schemas_sbs_path or sbs.default_schemas_sbs_path
    return chatter.create_sbs_repo(
        sbs.Repository(schemas_sbs_path / 'hat/monitor.sbs'),
        schemas_sbs_path=schemas_sbs_path)


def component_info_to_sbs(info):
    """Convert component info to SBS data

    Args:
        info (ComponentInfo): component info

    Returns:
        Any: SBS data

    """
    return {'cid': info.cid,
            'mid': info.mid,
            'name': info.name,
            'group': info.group,
            'address': _value_to_sbs_maybe(info.address),
            'rank': info.rank,
            'blessing': _value_to_sbs_maybe(info.blessing),
            'ready': _value_to_sbs_maybe(info.ready)}


def component_info_from_sbs(data):
    """Convert SBS data to component info

    Args:
        data (Any): SBS data

    Returns:
        ComponentInfo

    """
    return ComponentInfo(cid=data['cid'],
                         mid=data['mid'],
                         name=data['name'],
                         group=data['group'],
                         address=_value_from_sbs_maybe(data['address']),
                         rank=data['rank'],
                         blessing=_value_from_sbs_maybe(data['blessing']),
                         ready=_value_from_sbs_maybe(data['ready']))


def create_msg_client_sbs(name, group, address, ready):
    """Create MsgClient SBS data

    Args:
        name (str): component name
        group (str): component group
        address (Optional[str]): address
        ready (Optional[int]): ready token

    Returns:
        Any: SBS data

    """
    return {'name': name,
            'group': group,
            'address': _value_to_sbs_maybe(address),
            'ready': _value_to_sbs_maybe(ready)}


def _value_to_sbs_maybe(value):
    return ('Just', value) if value is not None else ('Nothing', None)


def _value_from_sbs_maybe(maybe):
    return maybe[1]
