import pytest
import datetime

import hat.syslog.common
from hat.syslog.server.common import (Entry, Filter,
                                      filter_to_json, filter_from_json,
                                      entry_to_json, entry_from_json)


@pytest.mark.parametrize("filter", [
    Filter(max_results=10,
           last_id=None,
           entry_timestamp_from=None,
           entry_timestamp_to=datetime.datetime.utcnow().timestamp(),
           facility=hat.syslog.common.Facility.KERNEL,
           severity=hat.syslog.common.Severity.CRITICAL,
           hostname='host',
           app_name='app1',
           procid='1234',
           msgid='msg.id',
           msg='this is message'),
    Filter(max_results=None,
           last_id=None,
           entry_timestamp_from=None,
           entry_timestamp_to=None,
           facility=hat.syslog.common.Facility.KERNEL,
           severity=hat.syslog.common.Severity.ERROR,
           hostname=None,
           app_name=None,
           procid=None,
           msgid=None,
           msg=None)])
def test_filter_json_serialization(filter):
    filter_json = filter_to_json(filter)
    assert filter == filter_from_json(filter_json)


@pytest.mark.parametrize("entry", [
    Entry(id=1,
          timestamp=datetime.datetime.utcnow().timestamp(),
          msg=hat.syslog.common.Msg(
              facility=hat.syslog.common.Facility.KERNEL,
              severity=hat.syslog.common.Severity.EMERGENCY,
              version=1,
              timestamp=None,
              hostname=None,
              app_name=None,
              procid=None,
              msgid=None,
              data=None,
              msg=None)),
    Entry(id=123456,
          timestamp=datetime.datetime.utcnow().timestamp(),
          msg=hat.syslog.common.Msg(
              facility=hat.syslog.common.Facility.KERNEL,
              severity=hat.syslog.common.Severity.ERROR,
              version=1,
              timestamp=None,
              hostname=None,
              app_name=None,
              procid=None,
              msgid=None,
              data=None,
              msg=None))])
def test_entry_json_serialization(entry):
    entry_json = entry_to_json(entry)
    assert entry == entry_from_json(entry_json)
