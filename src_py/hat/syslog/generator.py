"""Syslog test message generator"""

import argparse
import asyncio
import logging.config
import sys

from hat import aio


mlog: logging.Logger = logging.getLogger('hat.syslog.generator')
"""Module logger"""


def main():
    """Main entry point"""
    aio.init_asyncio()
    args = _create_parser().parse_args()
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'default': {}},
        'handlers': {
            'syslog': {
                'class': 'hat.syslog.handler.SysLogHandler',
                'host': 'localhost',
                'port': 6514,
                'comm_type': 'TCP',
                'level': 'DEBUG',
                'formatter': 'default',
                'queue_size': args.queue_size}},
        'root': {
            'level': 'INFO',
            'handlers': ['syslog']},
        'disable_existing_loggers': False})
    aio.run_asyncio(async_main(args))


async def async_main(args):
    """Async main

    Args:
        args: parsed command line arguments

    """
    for i in range(args.count):
        mlog.info(
            ('{} {:0' + str(_number_of_digits(args.count)) + '}').format(
                args.text, i))
        await asyncio.sleep(args.msg_delay)
    await asyncio.sleep(args.end_delay)


def _number_of_digits(x):
    if x < 10:
        return 1
    return 1 + _number_of_digits(x // 10)


def _create_parser():
    parser = argparse.ArgumentParser(prog='hat-syslog-generator')
    parser.add_argument(
        '--count', default=1, metavar='N', type=int,
        help="number of log messages (default 1)")
    parser.add_argument(
        '--text', default="syslog generator test", metavar='text',
        help="log message text (default 'syslog generator test')")
    parser.add_argument(
        '--queue-size', metavar='N', dest='queue_size', type=int, default=1024,
        help="client's log message queue size (default 1024)")
    parser.add_argument(
        '--msg-delay', metavar='t', dest='msg_delay', type=float, default=0.01,
        help="time delay between message generation (seconds) (default 0.01)")
    parser.add_argument(
        '--end-delay', metavar='t', dest='end_delay', type=float, default=0.5,
        help="time delay affter all messages have been generated "
             "(default 0.5)")
    return parser


if __name__ == '__main__':
    sys.exit(main())
