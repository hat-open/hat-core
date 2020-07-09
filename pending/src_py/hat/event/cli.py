import argparse
import asyncio
import contextlib
import csv
import datetime
import itertools
import sys

import hat.event.client

from hat import sbs
from hat import util
from hat.event import common
from hat.util import aio
from hat.util import json


def main():
    aio.init_asyncio()
    args = _create_parser().parse_args()
    sbs_repo = common.create_sbs_repo(args.schemas_sbs_path)

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(args, sbs_repo))


async def async_main(args, sbs_repo):
    address = f'tcp+sbs://{args.host}:{args.port}'
    subscriptions = args.subscriptions if args.command == 'subscribe' else None

    try:
        client = await hat.event.client.connect(
            sbs_repo, address, subscriptions=subscriptions)
    except Exception:
        print('unable to connect')
        sys.exit(1)

    printer = CsvPrinter(args) if args.csv else PrettyPrinter(args)
    f = {'query': _query,
         'register': _register,
         'subscribe': _subscribe}[args.command]
    await f(args, client, printer)


async def _query(args, client, printer):
    data = common.QueryData(
        event_ids=args.event_ids,
        event_types=args.event_types,
        t_from=args.t_from,
        t_to=args.t_to,
        source_t_from=args.source_t_from,
        source_t_to=args.source_t_to,
        payload=(common.EventPayload(type=common.EventPayloadType.JSON,
                                     data=json.encode(args.payload))
                 if args.payload is not None else None),
        order=args.order,
        order_by=args.order_by,
        unique_type=args.unique_type,
        max_results=args.max_results)
    events = await client.query(data)
    printer.print(events)


async def _register(args, client, printer):
    register_event = common.RegisterEvent(
        event_type=args.event_type,
        source_timestamp=args.source_timestamp,
        payload=(common.EventPayload(type=common.EventPayloadType.JSON,
                                     data=json.encode(args.payload))
                 if args.payload is not None else None))
    events = await client.register_with_response([register_event])
    printer.print(events)


async def _subscribe(args, client, printer):
    while True:
        events = await client.receive()
        printer.print(events)


class PrettyPrinter():

    def __init__(self, args):
        self._args = args
        self._first = True

    def print(self, events):
        alignment = 'rlllrrll' if self._args.unix_timestamp else 'rlllllll'
        headers = [
            '#',
            'Server',
            'Instance',
            'Event type',
            'Timestamp',
            'Source timestamp',
            'Payload type',
            'Payload data']
        rows = [(
            str(i+1),
            str(event.event_id.server),
            str(event.event_id.instance),
            ':'.join(event.event_type),
            _format_timestamp(self._args, event.timestamp),
            _format_timestamp(self._args, event.source_timestamp),
            *_format_payload(event.payload)
        ) for i, event in enumerate(events)]

        lengths = [0] * len(headers)
        for row in itertools.chain([headers], rows):
            for i, col in enumerate(row):
                lengths[i] = max(lengths[i], len(col))

        if not self._first:
            print("=" * (sum(lengths) + 2 * (len(headers) - 1)))
        self._first = False

        print("  ".join(header.ljust(l)
              for header, l in zip(headers, lengths)))
        print("  ".join("-" * l for l in lengths))

        for row in rows:
            print("  ".join(col.rjust(l) if align == 'r' else col.ljust(l)
                            for col, l, align
                            in zip(row, lengths, list(alignment))))

    def _format_timestamp(self, timestamp):
        if not timestamp:
            return '-'
        return (f'{common.timestamp_to_float(timestamp):.6f}'
                if self._args.unix_timestamp
                else common.timestamp_to_datetime(
                    timestamp).isoformat(timespec='microseconds'))


class CsvPrinter():

    def __init__(self, args):
        self._args = args
        self._writer = csv.writer(sys.stdout)
        self._writer.writerow([
            'server',
            'instance',
            'event_type',
            'timestamp',
            'source_timestamp',
            'payload_type',
            'payload_data'])

    def print(self, events):
        self._writer.writerows([
            event.event_id.server,
            event.event_id.instance,
            ':'.join(event.event_type),
            _format_timestamp(self._args, event.timestamp, default=''),
            _format_timestamp(self._args, event.source_timestamp, default=''),
            *_format_payload(event.payload, default='')
        ] for event in events)


def _format_timestamp(args, timestamp, default='-'):
    if not timestamp:
        return default
    return (f'{common.timestamp_to_float(timestamp):.6f}'
            if args.unix_timestamp
            else common.timestamp_to_datetime(
                timestamp).isoformat(timespec='microseconds'))


def _format_payload(payload, default='-'):
    if not payload:
        return (default, default)
    type = {common.EventPayloadType.BINARY: 'BINARY',
            common.EventPayloadType.JSON: 'JSON',
            common.EventPayloadType.SBS: 'SBS'}[payload.type]
    data = {common.EventPayloadType.BINARY: lambda: payload.data.hex(),
            common.EventPayloadType.JSON: lambda: payload.data,
            common.EventPayloadType.SBS: lambda: json.encode({
                'module': payload.data.module,
                'type': payload.data.type,
                'data': payload.data.data.hex()})
            }[payload.type]()
    return (type, data)


def _create_parser():
    parser = argparse.ArgumentParser(
        description="HAT event command line client",
        add_help=False)

    subparsers = parser.add_subparsers(
        title="commands",
        description="use `%(prog)s <command> --help` for more information "
                    "on a specific command",
        dest='command',
        required=True)

    query_parser = subparsers.add_parser(
        'query',
        description="query events",
        help="query events")
    query_parser.add_argument(
        '--id', nargs='+', metavar='event_id',
        action=_EventIdArgParseAction, default=None, dest='event_ids',
        help="one or more event ids in the form of <server>:<instance>")
    query_parser.add_argument(
        '--type', nargs='+', metavar='event_type',
        type=_parse_event_type, default=None, dest='event_types',
        help="one or more event types in the form of "
             "<subtype1>:<subtype2>:...")
    query_parser.add_argument(
        '--t-from', metavar='timestamp_from',
        type=_parse_timestamp, default=None, dest='t_from',
        help="timestamp from, as unix seconds or ISO 8601")
    query_parser.add_argument(
        '--t-to', metavar='timestamp_to',
        type=_parse_timestamp, default=None, dest='t_to',
        help="timestamp to, as unix seconds or ISO 8601")
    query_parser.add_argument(
        '--source-t-from', metavar='source_timestamp_from',
        type=_parse_timestamp, default=None, dest='source_t_from',
        help="source timestamp from, as unix seconds or ISO 8601")
    query_parser.add_argument(
        '--source-t-to', metavar='source_timestamp_to',
        type=_parse_timestamp, default=None, dest='source_t_to',
        help="source timestamp to, as unix seconds or ISO 8601")
    query_parser.add_argument(
        '--payload', metavar='payload',
        type=json.decode, default=None, dest='payload',
        help="payload, as JSON serializable string")
    query_parser.add_argument(
        '--ascending',
        action='store_const',
        const=common.Order.ASCENDING,
        default=common.Order.DESCENDING,
        dest='order',
        help="order ascending")
    query_parser.add_argument(
        '--order-by-source-t',
        action='store_const',
        const=common.OrderBy.SOURCE_TIMESTAMP,
        default=common.OrderBy.TIMESTAMP,
        dest='order_by',
        help="order by source timestamp")
    query_parser.add_argument(
        '--unique',
        action='store_true', dest='unique_type',
        help="unique event types")
    query_parser.add_argument(
        '--max-results', metavar='max_results',
        type=int, default=10, dest='max_results',
        help="maximum number of results (default: %(default)s)")

    register_parser = subparsers.add_parser(
        'register',
        description="register event",
        help="register event")
    register_parser.add_argument(
        '--source-timestamp', metavar='source_timestamp',
        type=_parse_timestamp, default=None, dest='source_timestamp',
        help="source timestamp, as unix seconds or ISO 8601")
    register_parser.add_argument(
        '--payload', metavar='payload',
        type=json.decode, default=None, dest='payload',
        help="payload, as JSON serializable string")
    register_parser.add_argument(
        'event_type',
        type=_parse_event_type,
        help="event type in the form of <subtype1>:<subtype2>:...")

    subscribe_parser = subparsers.add_parser(
        'subscribe',
        description="subscribe to and receive events",
        help="subscribe to and receive events")
    subscribe_parser.add_argument(
        'subscriptions', nargs='+', metavar='event_type',
        type=_parse_event_type,
        help="one or more event types in the form of "
             "<subtype1>:<subtype2>:...")

    opt_args = parser.add_argument_group('optional arguments')
    opt_args.add_argument(
        '--help',
        action='help',
        help="show this help message and exit")
    opt_args.add_argument(
        '-h', '--host', metavar='host',
        default='localhost', dest='host',
        help="event server host (default: %(default)s)")
    opt_args.add_argument(
        '-p', '--port', metavar='port',
        type=int, default=23012, dest='port',
        help="event server port (default: %(default)s)")
    opt_args.add_argument(
        '-u', '--unix-timestamp',
        action='store_true', dest='unix_timestamp',
        help="show timestamp as number of seconds since 1970-01-01")
    opt_args.add_argument(
        '-c', '--csv',
        action='store_true', dest='csv',
        help="format output as CSV")

    dev_args = parser.add_argument_group('development arguments')
    dev_args.add_argument(
        '--sbs-schemas-path', metavar='path', dest='schemas_sbs_path',
        default=sbs.default_schemas_sbs_path,
        action=util.EnvPathArgParseAction,
        help="override sbs schemas directory path")

    return parser


class _EventIdArgParseAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        ret = []
        for value in (values if self.nargs else [values]):
            args = value.split(':')
            if len(args) != 2:
                parser.error('invalid event_id format')
            try:
                ret.append(common.EventId(server=int(args[0]),
                                          instance=int(args[1])))
            except ValueError:
                parser.error('server and instance must be integers')
        setattr(namespace, self.dest, ret if self.nargs else ret[0])


def _parse_event_type(value):
    return value.split(':')


def _parse_timestamp(value):
    with contextlib.suppress(ValueError):
        return common.timestamp_from_float(float(value))
    try:
        return common.timestamp_from_datetime(
            datetime.datetime.fromisoformat(value))
    except Exception:
        raise argparse.ArgumentTypeError('invalid timestamp format')


if __name__ == '__main__':
    sys.exit(main())
