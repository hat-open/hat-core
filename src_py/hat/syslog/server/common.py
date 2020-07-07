"""Common data structures and functions"""

from hat import util
from hat.syslog.common import (Facility, Severity, Msg,
                               msg_from_str, msg_to_json, msg_from_json)


__all__ = ['Facility', 'Severity', 'Msg',
           'msg_from_str', 'msg_to_json',
           'Entry', 'Filter',
           'filter_to_json', 'filter_from_json', 'entry_to_json']


Entry = util.namedtuple(
    'Entry',
    ['id', 'int'],
    ['timestamp', 'float'],
    ['msg', 'Msg'])

Filter = util.namedtuple(
    'Filter',
    ['max_results', 'Optional[int]', None],
    ['last_id', 'Optional[int]', None],
    ['entry_timestamp_from', 'Optional[float]', None],
    ['entry_timestamp_to', 'Optional[float]', None],
    ['facility', 'Optional[Facility]', None],
    ['severity', 'Optional[Severity]', None],
    ['hostname', 'Optional[str]', None],
    ['app_name', 'Optional[str]', None],
    ['procid', 'Optional[str]', None],
    ['msgid', 'Optional[str]', None],
    ['msg', 'Optional[str]', None])


def filter_to_json(filter):
    """Convert filter to json data

    Args:
        filter (Filter): filter

    Returns:
        Any

    """
    return dict(filter._asdict(),
                facility=filter.facility.name if filter.facility else None,
                severity=filter.severity.name if filter.severity else None)


def filter_from_json(json_filter):
    """Create filter from json data

    Args:
        json_filter (Any): json data

    Returns:
        Filter

    """
    return Filter(**dict(
        json_filter,
        facility=(Facility[json_filter['facility']] if json_filter['facility']
                  else None),
        severity=(Severity[json_filter['severity']] if json_filter['severity']
                  else None)))


def entry_to_json(entry):
    """Convert entry to json data

    Args:
        entry (Entry): entry

    Returns:
        Any

    """
    return dict(entry._asdict(),
                msg=msg_to_json(entry.msg))


def entry_from_json(json_entry):
    """Create entry from json data

    Args:
        json_entry (Any): json data

    Returns:
        Entry

    """
    return Entry(**dict(
        json_entry,
        msg=msg_from_json(json_entry['msg'])))
