import asyncio
import contextlib
import datetime
import inspect
import logging.config
import os
import socket
import threading
import traceback
import time

import pytest

from hat import json

import hat.syslog.handler
import hat.syslog.server.conf
import hat.syslog.server.syslog

from test_unit.test_syslog.test_server import common
import pem


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


@pytest.fixture
async def message_queue(conf_syslog, pem_path):
    backend = common.create_backend('test_syslog.syslog')
    server = await hat.syslog.server.syslog.create_syslog_server(conf_syslog,
                                                                 backend)
    yield backend._msg_queue

    await server.async_close()
    assert server.is_closed


@pytest.fixture
def logger(syslog_port, comm_type):
    handler = hat.syslog.handler.SysLogHandler(host='127.0.0.1',
                                               port=syslog_port,
                                               comm_type=comm_type.upper(),
                                               queue_size=10)
    handler.setLevel('DEBUG')
    logger = logging.getLogger('test_syslog.syslog')
    logger.propagate = False
    logger.setLevel('DEBUG')
    logger.addHandler(handler)
    yield logger
    logger.removeHandler(handler)
    handler.close()
    time.sleep(0.01)


@pytest.mark.asyncio
async def test_msg(message_queue, logger):
    ts_before = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
    logger.info('for your information')
    lineno = inspect.currentframe().f_lineno - 1
    ts, msg = await message_queue.get()
    ts_after = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()

    assert ts_before < ts < ts_after
    assert msg.facility == hat.syslog.common.Facility.USER
    assert msg.severity == hat.syslog.common.Severity.INFORMATIONAL
    assert msg.version == 1
    assert ts_before < msg.timestamp < ts
    assert msg.hostname == socket.gethostname()

    # TODO pytest/__main__.py != pytest/__init__.py
    # assert msg.app_name == pytest.__file__

    assert int(msg.procid) == os.getpid()
    assert msg.msgid == logger.name
    assert msg.msg == 'for your information'

    msg_data = json.decode(msg.data)
    assert msg_data['hat@1']['name'] == logger.name
    assert int(msg_data['hat@1']['thread']) == threading.current_thread().ident
    assert msg_data['hat@1']['funcName'] == 'test_msg'
    assert int(msg_data['hat@1']['lineno']) == lineno
    assert not msg_data['hat@1']['exc_info']


@pytest.mark.asyncio
async def test_dropped(logger, conf_syslog, short_reconnect_delay):
    for i in range(20):
        logger.info('%s', i)
    backend = common.create_backend(logger.name)
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

    logger.info('%s', i)
    _, msg = await message_queue.get()
    assert int(msg.msg) == i
    assert message_queue.empty()

    await server.async_close()


@pytest.mark.skip(reason='WIP')
@pytest.mark.parametrize("root_level, levels_exp", [
    ('CRITICAL', ['CRITICAL']),
    ('ERROR', ['CRITICAL', 'ERROR']),
    ('WARNING', ['CRITICAL', 'ERROR', 'WARNING']),
    ('INFO', ['CRITICAL', 'ERROR', 'WARNING', 'INFORMATIONAL']),
    ('DEBUG', ['CRITICAL', 'ERROR', 'WARNING', 'INFORMATIONAL', 'DEBUG']),
    ])
@pytest.mark.asyncio
async def test_level(message_queue, logger, root_level, levels_exp):
    logger.setLevel(root_level)
    levels_res = []
    all_levels = [logging.CRITICAL, logging.ERROR, logging.WARNING,
                  logging.INFO, logging.DEBUG]
    for level in all_levels:
        logger.log(level, 'message on level %s', level)
    with contextlib.suppress(asyncio.TimeoutError):
        for _ in all_levels:
            _, msg = await asyncio.wait_for(message_queue.get(), 0.)
            levels_res.append(msg.severity.name)
    assert levels_res == levels_exp


@pytest.mark.asyncio
async def test_exc_info(message_queue, logger):
    try:
        raise Exception('Exception!')
    except Exception as e:
        logger.error('an exception occured: %s', e, exc_info=e)
        exc_info_exp = traceback.format_exc()
    ts, msg = await message_queue.get()
    msg_data = json.decode(msg.data)
    assert msg_data['hat@1']['exc_info'] == exc_info_exp
    assert msg.msg == 'an exception occured: Exception!'
