"""Configuration parser

Attributes:
    mlog (logging.Logger): module logger
    package_path (pathlib.Path): `hat.syslog.server` package directory
    user_data_dir (pathlib.Path): XDG user data directory
    user_conf_dir (pathlib.Path): XDG user conf directory
    default_ui_path (pathlib.Path): default ui directory
    default_conf_path (pathlib.Path): default conf path

"""

from pathlib import Path
import argparse
import logging

import appdirs

from hat import json
from hat import util
from hat.syslog import common


mlog = logging.getLogger(__name__)

package_path = Path(__file__).parent
user_data_dir = Path(appdirs.user_data_dir('hat'))
user_conf_dir = Path(appdirs.user_config_dir('hat'))

default_ui_path = package_path / 'ui'
default_conf_path = user_conf_dir / 'syslog.yaml'


SysLogServerConf = util.namedtuple(
    'SysLogServerConf',
    ['addr', 'str: listening address', 'tcp://0.0.0.0:6514'],
    ['pem', 'Optional[Path]: pem file path', None])

WebServerConf = util.namedtuple(
    'WebServerConf',
    ['addr', 'str: listening address', 'http://0.0.0.0:23020'],
    ['pem', 'Optional[Path]: pem file path', None],
    ['path', 'Path: static ui files path', default_ui_path])

BackendConf = util.namedtuple(
    'BackendConf',
    ['path', 'Path: database file path', user_data_dir / 'syslog.db'],
    ['low_size', 'int: low size count', int(1e6)],
    ['high_size', 'int: high size count', int(1e7)],
    ['enable_archive', 'bool: enable archive flag', False],
    ['disable_journal', 'bool: disable journal flag', False])

Conf = util.namedtuple(
    'Conf',
    ['log', 'Any: logging configuration', {'version': 1}],
    ['syslog', 'SysLogServerConf', SysLogServerConf()],
    ['ui', 'WebServerConf', WebServerConf()],
    ['db', 'BackendConf', BackendConf()])


def get_conf():
    """Get configuration data

    Returns:
        Conf

    """
    args = _create_parser().parse_args()

    if args.conf.exists():
        json_conf = json.decode_file(args.conf)
        json_schema_repo = common.json_schema_repo
        json_schema_repo.validate('hat://syslog.yaml#', json_conf)
        conf = _parse_json_conf(json_conf)
    else:
        conf = Conf()

    return conf._replace(
        log=_update_log_conf(conf.log, args),
        syslog=_update_syslog_conf(conf.syslog, args),
        ui=_update_ui_conf(conf.ui, args),
        db=_update_db_conf(conf.db, args))


def _parse_json_conf(json_conf):
    return Conf(
        log=json_conf['log'],
        syslog=SysLogServerConf(
            addr=json_conf['syslog_addr'],
            pem=(Path(json_conf['syslog_pem'])
                 if 'syslog_pem' in json_conf
                 else None)),
        ui=WebServerConf(
            addr=json_conf['ui_addr'],
            pem=(Path(json_conf['ui_pem'])
                 if 'ui_pem' in json_conf
                 else None)),
        db=BackendConf(
            path=Path(json_conf['db_path']),
            low_size=json_conf['db_low_size'],
            high_size=json_conf['db_high_size'],
            enable_archive=json_conf['db_enable_archive'],
            disable_journal=json_conf['db_disable_journal']))


def _update_log_conf(log_conf, args):
    if not args.log:
        return log_conf
    return {
        'version': 1,
        'formatters': {
            'syslog_server_console': {
                'format': '[%(asctime)s %(levelname)s %(name)s] %(message)s'}},
        'handlers': {
            'syslog_server_console': {
                'class': 'logging.StreamHandler',
                'formatter': 'syslog_server_console',
                'level': args.log}},
        'loggers': {
            'hat.syslog': {
                'level': args.log}},
        'root': {
            'level': 'INFO' if args.log == 'DEBUG' else args.log,
            'handlers': ['syslog_server_console']},
        'disable_existing_loggers': False}


def _update_syslog_conf(syslog_conf, args):
    return syslog_conf._replace(
        addr=(args.syslog_addr
              if args.syslog_addr is not None
              else syslog_conf.addr),
        pem=(Path(args.syslog_pem)
             if args.syslog_pem is not None
             else syslog_conf.pem))


def _update_ui_conf(ui_conf, args):
    return ui_conf._replace(
        addr=(args.ui_addr
              if args.ui_addr is not None
              else ui_conf.addr),
        pem=(Path(args.ui_pem)
             if args.ui_pem is not None
             else ui_conf.pem),
        path=args.ui_path)


def _update_db_conf(db_conf, args):
    return db_conf._replace(
        path=(Path(args.db_path)
              if args.db_path is not None
              else db_conf.path),
        low_size=(args.db_low_size
                  if args.db_low_size is not None
                  else db_conf.low_size),
        high_size=(args.db_high_size
                   if args.db_high_size is not None
                   else db_conf.high_size),
        enable_archive=args.db_enable_archive or db_conf.enable_archive,
        disable_journal=args.db_disable_journal or db_conf.disable_journal)


def _create_parser():
    default_conf = Conf()

    parser = argparse.ArgumentParser(prog='hat-syslog')
    parser.add_argument(
        '--conf', metavar='path',
        default=default_conf_path, type=Path,
        help="configuration defined by hat://syslog/server.yaml# "
             "(default $XDG_CONFIG_HOME/hat/syslog.yaml)")

    conf_args = parser.add_argument_group('configuration arguments')
    conf_args.add_argument(
        '--log', metavar='level', dest='log',
        default=None, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help="console log level")
    conf_args.add_argument(
        '--syslog-addr', metavar='address', dest='syslog_addr',
        default=None,
        help="syslog listening address "
             f"(default: {default_conf.syslog.addr})")
    conf_args.add_argument(
        '--syslog-pem', metavar='path', dest='syslog_pem',
        default=None,
        help="pem file path - mandatory for ssl communication")
    conf_args.add_argument(
        '--ui-addr', metavar='address', dest='ui_addr',
        default=None,
        help="ui listening address "
             f"(default: {default_conf.ui.addr})")
    conf_args.add_argument(
        '--ui-pem', metavar='path', dest='ui_pem',
        default=None,
        help="pem file path - mandatory for https communication")
    conf_args.add_argument(
        '--db-path', metavar='path', dest='db_path',
        default=None,
        help="sqlite database file path (default: $HATPATH/syslog.db)")
    conf_args.add_argument(
        '--db-low-size', metavar='count', dest='db_low_size',
        default=None, type=int,
        help="number of messages kept in database after database cleanup "
             f"(default: {default_conf.db.low_size})")
    conf_args.add_argument(
        '--db-high-size', metavar='count', dest='db_high_size',
        default=None, type=int,
        help="number of messages that will trigger database cleanup "
             f"(default: {default_conf.db.high_size})")
    conf_args.add_argument(
        '--db-enable-archive', dest='db_enable_archive',
        action='store_true',
        help="should messages, deleted during database cleanup, be kept "
             "in archive files")
    conf_args.add_argument(
        '--db-disable-journal', dest='db_disable_journal',
        action='store_true',
        help="disable sqlite jurnaling")

    dev_args = parser.add_argument_group('development arguments')
    dev_args.add_argument(
        '--ui-path', metavar='path', dest='ui_path',
        default=default_ui_path, type=Path,
        help="override web ui directory path")

    return parser
