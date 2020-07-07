import asyncio
import contextlib
import datetime
import inspect
import logging.config
import os
import socket
import threading
import traceback

import pytest

from hat.util import json

import hat.syslog.handler
import hat.syslog.server.conf
import hat.syslog.server.syslog

from test_unit.test_syslog.test_server import common
import pem


mlog = logging.getLogger('test_syslog.syslog')


@pytest.fixture
def syslog_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture(params=['tcp', 'ssl'])
def comm_type(request):
    return request.param


@pytest.fixture
def syslog_address(syslog_port, comm_type):
    return f"{comm_type}://0.0.0.0:{syslog_port}"


@pytest.fixture
def conf_logging(syslog_port, comm_type):
    return {
        'version': 1,
        'formatters': {'default': {}},
        'handlers': {
            'syslog': {
                'class': 'hat.syslog.handler.SysLogHandler',
                'host': 'localhost',
                'port': syslog_port,
                'comm_type': comm_type.upper(),
                'level': 'DEBUG',
                'formatter': 'default',
                'queue_size': 10}},
        'root': {
                'level': 'INFO',
                'handlers': ['syslog']},
        'disable_existing_loggers': False}


@pytest.fixture
def short_reconnect_delay(monkeypatch):
    monkeypatch.setattr(hat.syslog.handler, 'reconnect_delay', 0.001)


@pytest.fixture(scope="session")
def pem_path(tmp_path_factory):
    path = tmp_path_factory.mktemp('syslog') / 'pem'
    pem.create_pem_file(path)
    return path


@pytest.fixture
def conf_syslog(syslog_address, pem_path):
    return hat.syslog.server.conf.SysLogServerConf(addr=syslog_address,
                                                   pem=pem_path)


@pytest.mark.asyncio
@pytest.fixture
async def message_queue(conf_logging, conf_syslog, pem_path):
    logging.config.dictConfig(conf_logging)
    backend = common.create_backend(mlog.name)
    server = await hat.syslog.server.syslog.create_syslog_server(conf_syslog,
                                                                 backend)
    yield backend._msg_queue

    await server.async_close()
    assert server.closed.done()


@pytest.mark.asyncio
async def test_msg(message_queue, conf_logging):
    ts_before = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
    mlog.info('for your information')
    lineno = inspect.currentframe().f_lineno - 1
    ts, msg = await message_queue.get()
    ts_after = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()

    assert ts_before < ts < ts_after
    assert msg.facility == hat.syslog.common.Facility.USER
    assert msg.severity == hat.syslog.common.Severity.INFORMATIONAL
    assert msg.version == conf_logging['version']
    assert ts_before < msg.timestamp < ts
    assert msg.hostname == socket.gethostname()

    # TODO pytest/__main__.py != pytest/__init__.py
    # assert msg.app_name == pytest.__file__

    assert int(msg.procid) == os.getpid()
    assert msg.msgid == mlog.name
    assert msg.msg == 'for your information'

    msg_data = json.decode(msg.data)
    assert msg_data['hat@1']['name'] == mlog.name
    assert int(msg_data['hat@1']['thread']) == threading.current_thread().ident
    assert msg_data['hat@1']['funcName'] == 'test_msg'
    assert int(msg_data['hat@1']['lineno']) == lineno
    assert not msg_data['hat@1']['exc_info']


@pytest.mark.asyncio
async def test_dropped(conf_logging, conf_syslog, short_reconnect_delay):
    logging.config.dictConfig(conf_logging)
    for i in range(20):
        mlog.info('%s', i)
    backend = common.create_backend(mlog.name)
    server = await hat.syslog.server.syslog.create_syslog_server(conf_syslog,
                                                                 backend)
    message_queue = backend._msg_queue
    assert message_queue.empty()
    _, msg_drop = await message_queue.get()

    assert msg_drop.msg == 'dropped 10 log messages'
    assert msg_drop.severity == hat.syslog.common.Severity.ERROR
    for i in range(10, 20):
        _, msg = await message_queue.get()
        assert int(msg.msg) == i
    assert message_queue.empty()

    mlog.info('%s', i)
    _, msg = await message_queue.get()
    assert int(msg.msg) == i
    assert message_queue.empty()

    await server.async_close()


@pytest.mark.parametrize("root_level, levels_exp", [
    ('CRITICAL', ['CRITICAL']),
    ('ERROR', ['CRITICAL', 'ERROR']),
    ('WARNING', ['CRITICAL', 'ERROR', 'WARNING']),
    ('INFO', ['CRITICAL', 'ERROR', 'WARNING', 'INFORMATIONAL']),
    ('DEBUG', ['CRITICAL', 'ERROR', 'WARNING', 'INFORMATIONAL', 'DEBUG']),
    ])
@pytest.mark.asyncio
async def test_level(conf_logging, message_queue, root_level,
                     levels_exp):
    conf_logging['root']['level'] = root_level
    logging.config.dictConfig(conf_logging)

    levels_res = []
    for level in ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']:
        getattr(mlog, level.lower())('message on level %s', level)
        with contextlib.suppress(asyncio.TimeoutError):
            _, msg = await asyncio.wait_for(message_queue.get(), 0.05)
            levels_res.append(msg.severity.name)
    assert levels_res == levels_exp


@pytest.mark.asyncio
async def test_exc_info(message_queue, conf_logging):
    try:
        raise Exception('Exception!')
    except Exception as e:
        mlog.error('an exception occured: %s', e, exc_info=e)
        exc_info_exp = traceback.format_exc()
    ts, msg = await message_queue.get()
    msg_data = json.decode(msg.data)
    assert msg_data['hat@1']['exc_info'] == exc_info_exp
    assert msg.msg == 'an exception occured: Exception!'
