"""Common functionality shared between clients and monitor server"""

from pathlib import Path

from hat import chatter
from hat import json
from hat import sbs
from hat import util


package_path = Path(__file__).parent

json_schema_repo = json.SchemaRepository(
    json.json_schema_repo,
    json.SchemaRepository.from_json(package_path / 'json_schema_repo.json'))

sbs_repo = sbs.Repository(
    chatter.sbs_repo,
    sbs.Repository.from_json(package_path / 'sbs_repo.json'))


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


def component_info_to_sbs(info):
    """Convert component info to SBS data

    Args:
        info (ComponentInfo): component info

    Returns:
        hat.sbs.Data: SBS data

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
        data (hat.sbs.Data): SBS data

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
        hat.sbs.Data: SBS data

    """
    return {'name': name,
            'group': group,
            'address': _value_to_sbs_maybe(address),
            'ready': _value_to_sbs_maybe(ready)}


def _value_to_sbs_maybe(value):
    return ('Just', value) if value is not None else ('Nothing', None)


def _value_from_sbs_maybe(maybe):
    return maybe[1]
