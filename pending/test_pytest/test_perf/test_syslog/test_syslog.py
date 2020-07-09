import pytest
import yaml
import psutil
import signal
import sys
import logging
import logging.config

from hat import util
from hat.util import json

mlog = logging.getLogger(__name__)


@pytest.fixture
def syslog_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def conf(syslog_port, unused_tcp_port_factory, tmp_path):
    syslog_ui_port = unused_tcp_port_factory()
    return {
        'type': 'syslog',
        'version': '0.0',
        'log': {
            'version': 1,
            'formatters': {'default': {}},
            'handlers': {
                'syslog': {
                    'class': 'hat.syslog.handler.SysLogHandler',
                    'host': 'localhost',
                    'port': syslog_port,
                    'comm_type': 'TCP',
                    'level': 'DEBUG',
                    'formatter': 'default',
                    'queue_size': 1000000}},
            'root': {
                    'level': 'INFO',
                    'handlers': ['syslog']},
            'disable_existing_loggers': False},
        'syslog_addr': f'tcp://0.0.0.0:{syslog_port}',
        'ui_addr': f'http://0.0.0.0:{syslog_ui_port}',
        'db_path': str(tmp_path / 'syslog.db'),
        'db_low_size': 1000000,
        'db_high_size': 10000000,
        'db_enable_archive': False,
        'db_disable_journal': False}


@pytest.mark.asyncio
@pytest.fixture
async def create_syslog_server(tmp_path, syslog_port):

    async def wrapper(conf, backend_type='sqlite', message_count=None):
        logging.config.dictConfig(conf['log'])

        conf_path = tmp_path / 'syslog.yaml'
        with open(conf_path, 'w', encoding='utf-8') as f:
            yaml.dump(conf, f)
        cmd = [
            'python', '-m', 'test_perf.test_syslog.mock_main',
            '--conf', tmp_path / str(conf_path),
            '--json-schemas-path', str(json.default_schemas_json_path),
            '--ui-path', str(tmp_path),
            backend_type]
        if message_count:
            cmd.append(str(message_count))
        p = psutil.Popen(cmd)

        wait_until(process_is_running, p)
        wait_until(process_listens_on, p, syslog_port)
        return p

    return wrapper


def close_process(process):
    if not process_is_running(process):
        return
    process.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == 'win32'
                        else signal.SIGTERM)
    try:
        process.wait(5)
    except psutil.TimeoutExpired:
        process.kill()


def process_is_running(process):
    return process.is_running() and process.status() != 'zombie'


def process_listens_on(process, port):
    return bool(util.first(process.connections(),
                           lambda i: i.status == 'LISTEN' and
                           i.laddr.port == port))


def process_not_listen_on(process, port):
    return not process_listens_on(process, port)


def wait_until(fn, *args):
    while True:
        if fn(*args):
            return


@pytest.mark.parametrize("backend_type", ["memory", "sqlite"])
@pytest.mark.parametrize("message_count", [10, 1000, 10000])
@pytest.mark.asyncio
async def test_sqlite_vs_memory(conf, duration, create_syslog_server,
                                backend_type, message_count, syslog_port):
    process = await create_syslog_server(conf, backend_type, message_count)

    with duration(f"backend {backend_type} {message_count} messages "):
        for _ in range(message_count):
            mlog.info('fyi')
        wait_until(process_not_listen_on, process, syslog_port)

    close_process(process)


@pytest.mark.parametrize("disable_journal", [False, True])
@pytest.mark.parametrize("message_count", [10, 1000, 10000, 100000])
@pytest.mark.asyncio
async def test_journal(conf, duration, create_syslog_server,
                       message_count, disable_journal, syslog_port):
    conf['disable_journal'] = disable_journal
    process = await create_syslog_server(conf, message_count=message_count)

    with duration(f"{message_count} messages "
                  f"{'with journal' if not disable_journal else ''}"):
        for _ in range(message_count):
            mlog.info('fyi')
        wait_until(process_not_listen_on, process, syslog_port)

    close_process(process)
