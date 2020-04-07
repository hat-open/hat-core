import datetime

import pytest

from hat import sqlite3


@pytest.mark.parametrize("t", [
    datetime.datetime.now(),
    datetime.datetime(2000, 1, 1),
    datetime.datetime(2000, 1, 2, 3, 4, 5, 123456),
    datetime.datetime(2000, 1, 2, 3, 4, 5, 123456,
                      tzinfo=datetime.timezone.utc),
    datetime.datetime(2000, 1, 2, 3, 4, 5, 123456,
                      tzinfo=datetime.timezone(datetime.timedelta(hours=1,
                                                                  minutes=2))),
    datetime.datetime(2000, 1, 2, 3, 4, 5, 123456,
                      tzinfo=datetime.timezone(-datetime.timedelta(hours=1,
                                                                   minutes=2)))
])
def test_monkeypatch_sqlite3(t):
    with sqlite3.connect(':memory:',
                         isolation_level=None,
                         detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        conn.execute("CREATE TABLE test (t TIMESTAMP)")
        conn.execute("INSERT INTO test VALUES (:t)", {'t': t})
        result = conn.execute("SELECT t FROM test").fetchone()[0]
        assert result == t
