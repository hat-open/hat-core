import pytest
import sys
from pathlib import Path

from hat import json
import hat.syslog.server.conf


@pytest.fixture
def conf_path(tmp_path):
    return tmp_path / 'syslog.yaml'


@pytest.fixture
def conf_json(conf_path, tmp_path):
    return {
        'type': 'syslog',
        'version': '1',
        'log': {'version': 1,
                'formatters': {'default': {}},
                'handlers': {
                    'syslog': {
                        'class': 'hat.syslog.handler.SysLogHandler',
                        'host': 'localhost',
                        'port': 6514,
                        'comm_type': 'TCP',
                        'level': 'DEBUG',
                        'formatter': 'default',
                        'queue_size': 10}},
                'root': {
                        'level': 'INFO',
                        'handlers': ['syslog']},
                'disable_existing_loggers': False},
        'syslog_addr': 'tcp://0.0.0.0:6514',
        'syslog_pem': str(tmp_path / 'syslog.pem'),
        'ui_addr': 'http://0.0.0.0:23040',
        'ui_pem': str(tmp_path / 'ui.pem'),
        'db_path': str(tmp_path / 'syslog.db'),
        'db_low_size': 10000,
        'db_high_size': 10000,
        'db_enable_archive': True,
        'db_disable_journal': False}


def test_conf(conf_json, conf_path, monkeypatch):
    json.encode_file(conf_json, conf_path)
    monkeypatch.setattr(sys, 'argv', ['hat-syslog', '--conf', str(conf_path)])
    conf = hat.syslog.server.conf.get_conf()

    assert isinstance(conf, hat.syslog.server.conf.Conf)

    assert conf.log == conf_json['log']

    assert conf.syslog.addr == conf_json['syslog_addr']
    assert conf.syslog.pem == Path(conf_json['syslog_pem'])

    assert conf.ui.addr == conf_json['ui_addr']
    assert conf.ui.pem == Path(conf_json['ui_pem'])
    assert conf.ui.path

    assert conf.db.path == Path(conf_json['db_path'])
    assert conf.db.low_size == conf_json['db_low_size']
    assert conf.db.high_size == conf_json['db_high_size']
    assert conf.db.enable_archive == conf_json['db_enable_archive']
    assert conf.db.disable_journal == conf_json['db_disable_journal']


@pytest.mark.parametrize("arg_name, arg_value, attrs, value_exp", [
    ('--syslog-addr', 'tcp://0.0.0.0:12345', ['syslog', 'addr'],
     'tcp://0.0.0.0:12345'),
    ('--syslog-pem', 'pems/syslogpem.pem', ['syslog', 'pem'],
     Path('pems/syslogpem.pem')),
    ('--ui-addr', 'http://0.0.0.0:23041', ['ui', 'addr'],
     'http://0.0.0.0:23041'),
    ('--ui-pem', 'pems/syslogpem.pem', ['ui', 'pem'],
     Path('pems/syslogpem.pem')),
    ('--db-path', 'dbs/syslog.db', ['db', 'path'], Path('dbs/syslog.db')),
    ('--db-low-size', '1234', ['db', 'low_size'], 1234),
    ('--db-high-size', '4321', ['db', 'high_size'], 4321),
    ('--db-enable-archive', None, ['db', 'enable_archive'], True),
    ('--db-disable-journal', None, ['db', 'disable_journal'], True),
    ])
def test_override_from_args(conf_json, conf_path, monkeypatch,
                            arg_name, arg_value, attrs, value_exp):
    json.encode_file(conf_json, conf_path)
    args = ['hat-syslog', '--conf', str(conf_path), arg_name]
    if arg_value is not None:
        args.append(arg_value)
    monkeypatch.setattr(sys, 'argv', args)
    conf = hat.syslog.server.conf.get_conf()

    assert getattr(getattr(conf, attrs[0]), attrs[1]) == value_exp


def test_empty_conf(monkeypatch):
    monkeypatch.setattr(sys, 'argv', [])
    conf = hat.syslog.server.conf.get_conf()

    assert conf == hat.syslog.server.conf.Conf()
