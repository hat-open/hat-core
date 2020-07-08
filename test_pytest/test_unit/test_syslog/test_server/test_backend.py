import asyncio
import pytest
import datetime
import socket
import os

from hat import util
from hat.util import aio
import hat.syslog.server.backend
import hat.syslog.server.conf
import hat.syslog.server.common as server_common


def ts_now():
    return datetime.datetime.now(tz=datetime.timezone.utc).timestamp()


@pytest.fixture
def short_register_delay(monkeypatch):
    monkeypatch.setattr(hat.syslog.server.backend, "register_delay", 0.0)


@pytest.fixture(params=["delay", "queue_treshold"])
def force_delay_or_queue_threshold(monkeypatch, request):
    if request.param == "delay":
        monkeypatch.setattr(hat.syslog.server.backend,
                            "register_queue_treshold", 100)
        monkeypatch.setattr(hat.syslog.server.backend, "register_delay", 0.01)
    elif request.param == "queue_treshold":
        monkeypatch.setattr(hat.syslog.server.backend,
                            "register_delay", 1)


@pytest.fixture
def conf_db(tmp_path):
    path_db = tmp_path / 'syslog.db'
    return hat.syslog.server.conf.BackendConf(
        path=path_db,
        low_size=50,
        high_size=100,
        enable_archive=True,
        disable_journal=False)


@pytest.mark.asyncio
@pytest.fixture
async def backend(conf_db, short_register_delay):
    backend = await hat.syslog.server.backend.create_backend(conf_db)

    yield backend

    await backend.async_close()
    assert backend.closed.done()


@pytest.fixture
def message_factory():
    counter = 0

    def f(facility=server_common.Facility.USER,
          severity=server_common.Severity.ERROR,
          timestamp=ts_now(),
          hostname=socket.gethostname(),
          app_name=pytest.__file__,
          procid=os.getpid()):
        nonlocal counter
        counter += 1
        return server_common.Msg(
            facility=facility,
            severity=severity,
            version=1,
            timestamp=timestamp,
            hostname=hostname,
            app_name=app_name,
            procid=str(procid),
            msgid='test_syslog.backend',
            data="",
            msg=f'message no {counter}')

    return f


@pytest.mark.asyncio
async def test_register(backend, message_factory):
    entry_queue = aio.Queue()
    backend.register_change_cb(lambda e: entry_queue.put_nowait(e))

    assert backend.first_id is None
    assert backend.last_id is None

    for i in range(10):
        ts = ts_now()
        msg = message_factory()
        await backend.register(ts, msg)

        entries = await entry_queue.get()
        entry = entries[0]
        assert entry.id == i + 1
        assert entry.timestamp == ts
        assert entry.msg == msg
        assert backend.first_id == 1
        assert backend.last_id == entry.id


@pytest.mark.asyncio
async def test_register_with_delay(conf_db, message_factory,
                                   force_delay_or_queue_threshold):
    backend = await hat.syslog.server.backend.create_backend(conf_db)
    entry_queue = aio.Queue()
    backend.register_change_cb(lambda e: entry_queue.put_nowait(e))
    size = 100
    for i in range(size):
        await backend.register(ts_now(), message_factory())

    entries = []
    while len(entries) != size:
        entries += await entry_queue.get()
    assert entry_queue.empty()

    await backend.async_close()


@pytest.mark.asyncio
async def test_query(backend, message_factory):
    change_queue = aio.Queue()
    backend.register_change_cb(lambda _: change_queue.put_nowait(None))
    facilities = [server_common.Facility[i]
                  for i in ['USER', 'USER', 'KERNEL', 'KERNEL', 'MAIL']]
    severities = [server_common.Severity[i] for i in
                  ['CRITICAL', 'ERROR', 'WARNING', 'INFORMATIONAL', 'DEBUG']]
    hosts = [f'h{i}' for i in range(1, 6)]
    apps = [f'app{i}' for i in range(1, 6)]
    procids = [f'{i:04}' for i in range(1, 6)]
    msgs = []
    for _ in range(3):
        for facility, severity, host, app, procid in zip(
                facilities, severities, hosts, apps, procids):
            msg = message_factory(
                facility=facility, severity=severity, hostname=host,
                app_name=app, procid=procid)
            msgs.insert(0, msg)
            await backend.register(ts_now(), msg)
            await change_queue.get()

    query_res = await backend.query(server_common.Filter())
    assert [e.msg for e in query_res] == msgs
    assert len(set(e.id for e in query_res)) == len(msgs)

    query_res = await backend.query(server_common.Filter(max_results=3))
    assert [e.msg for e in query_res] == msgs[:3]

    query_res = await backend.query(server_common.Filter(last_id=10))
    assert [e.id for e in query_res] == [i for i in reversed(range(1, 11))]
    assert [e.msg for e in query_res] == msgs[-10:]

    for facility, severity, hostname, app_name, procid in zip(
            facilities, severities, hosts, apps, procids):
        query_res = await backend.query(server_common.Filter(
            facility=facility,
            severity=severity,
            hostname=hostname,
            app_name=app_name,
            procid=procid))
        assert len(query_res) == 3
        assert all(e.msg.facility == facility for e in query_res)
        assert all(e.msg.severity == severity for e in query_res)
        assert all(e.msg.hostname == hostname for e in query_res)
        assert all(e.msg.app_name == app_name for e in query_res)
        assert all(e.msg.procid == procid for e in query_res)

    query_res = await backend.query(server_common.Filter(
        msgid='test_syslog.backend'))
    assert len(query_res) == len(msgs)

    query_res = await backend.query(server_common.Filter(msg='message no 3'))
    assert len(query_res) == 1
    assert query_res[0].msg.msg == 'message no 3'

    query_res = await backend.query(server_common.Filter(msg='message no'))
    assert len(query_res) == len(msgs)

    query_res = await backend.query(server_common.Filter(
        entry_timestamp_from=0,
        entry_timestamp_to=ts_now(),
        facility=server_common.Facility.USER,
        severity=server_common.Severity.CRITICAL,
        hostname='h1',
        app_name='app1',
        procid='0001',
        msgid='test_syslog.backend',
        msg='message no 1'))
    assert len(query_res) == 2


@pytest.mark.parametrize("time_filter, exp_ts_ind", [
    ({'from': 0}, [0, 1, 2]),
    ({'from': 1}, [1, 2]),
    ({'from': 2}, [2]),
    ({'to': 0}, [0]),
    ({'to': 1}, [0, 1]),
    ({'to': 2}, [0, 1, 2]),
    ({'from': 1, 'to': 1}, [1]),
    ({'from': 0, 'to': 2}, [0, 1, 2]),
])
@pytest.mark.asyncio
async def test_query_on_timestamp(backend, message_factory,
                                  time_filter, exp_ts_ind):
    change_queue = aio.Queue()
    backend.register_change_cb(lambda _: change_queue.put_nowait(None))
    msgs = []
    ts = ts_now()
    tss = [ts - 20, ts - 10, ts]
    for ts in tss:
        for _ in range(5):
            msg = message_factory(timestamp=ts)
            msgs.insert(0, msg)
            await backend.register(ts, msg)
            await change_queue.get()

    filter = server_common.Filter(
        **{'entry_timestamp_' + k: tss[v] for k, v in time_filter.items()})
    query_res = await backend.query(filter)
    assert len(query_res) == len(exp_ts_ind) * 5
    assert all(e.timestamp in [tss[i] for i in exp_ts_ind] for e in query_res)


@pytest.mark.parametrize("enable_archive", [False, True])
@pytest.mark.asyncio
async def test_archive(conf_db, message_factory, short_register_delay,
                       enable_archive):
    conf_db = conf_db._replace(enable_archive=enable_archive)
    backend = await hat.syslog.server.backend.create_backend(conf_db)
    change_queue = aio.Queue()
    backend.register_change_cb(lambda e: change_queue.put_nowait(e))
    entries = []
    for _ in range(conf_db.high_size):
        await backend.register(ts_now(), message_factory())
        entries = await change_queue.get() + entries

    # wait for posible background db cleanup
    await asyncio.sleep(0.1)

    assert backend.last_id == conf_db.high_size
    assert backend.first_id == 1
    result = await backend.query(server_common.Filter())
    assert len(result) == conf_db.high_size
    count = len(list(conf_db.path.parent.glob(f'{conf_db.path.name}.*')))
    assert count == 0

    await backend.register(ts_now(), message_factory())
    entries = await change_queue.get() + entries

    # wait for expected background db cleanup
    await asyncio.sleep(0.1)

    assert backend.first_id == backend.last_id - conf_db.low_size + 1
    assert backend.last_id == conf_db.high_size + 1
    result = await backend.query(server_common.Filter())
    assert len(result) == conf_db.low_size
    count = len(list(conf_db.path.parent.glob(f'{conf_db.path.name}.*')))
    assert count == (1 if enable_archive else 0)

    await backend.async_close()
    assert backend.closed.done()

    if enable_archive:
        archive_path = util.first(conf_db.path.parent.glob('*.*'),
                                  lambda i: i.name == 'syslog.db.1')
        conf_db = conf_db._replace(path=archive_path)
        backend = await hat.syslog.server.backend.create_backend(conf_db)
        assert not backend.closed.done()

        entries_archived = await backend.query(server_common.Filter())
        assert len(entries_archived) == (conf_db.high_size -
                                         conf_db.low_size + 1)
        assert result + entries_archived == entries

        await backend.async_close()
        assert backend.closed.done()


@pytest.mark.asyncio
async def test_persistence(conf_db, message_factory):
    backend = await hat.syslog.server.backend.create_backend(conf_db)
    size = 100
    for _ in range(size):
        await backend.register(ts_now(), message_factory())

    query_res = []
    while len(query_res) != size:
        query_res = await backend.query(server_common.Filter())

    await backend.async_close()

    backend = await hat.syslog.server.backend.create_backend(conf_db)
    query_res_after = await backend.query(server_common.Filter())
    assert query_res_after == query_res

    await backend.async_close()


@pytest.mark.asyncio
async def test_entry_id_unique(backend, message_factory,
                               short_register_delay):
    entry_queue = aio.Queue()
    backend.register_change_cb(lambda e: entry_queue.put_nowait(e))
    size = 30
    blocks = 1
    entries = []
    for i in range(1, blocks + 1):
        for j in range(1, size + 1):
            await backend.register(ts_now(), message_factory())
            entries += await entry_queue.get()

    assert sorted(e.id for e in entries) == list(range(1, blocks * size + 1))


@pytest.mark.parametrize("disable_journal", [False, True])
@pytest.mark.asyncio
async def test_disable_journal(conf_db, message_factory, short_register_delay,
                               disable_journal):
    conf_db = conf_db._replace(disable_journal=disable_journal)
    backend = await hat.syslog.server.backend.create_backend(conf_db)

    async with aio.Group() as group:
        for _ in range(10):
            group.spawn(backend.register, ts_now(), message_factory())

    fnames = set()
    if not disable_journal:
        while 'syslog.db-journal' not in fnames:
            fnames.update(i.name for i in conf_db.path.parent.glob('*.*'))
    else:
        for i in range(100):
            fnames.update(i.name for i in conf_db.path.parent.glob('*.*'))
        assert 'syslog.db-journal' not in fnames

    await backend.async_close()
