import struct
import typing

from hat import json
from hat.event.server.backends.lmdb import common


def encode_event(event: common.Event) -> bytes:
    event_sbs = common.event_to_sbs(event)
    return common.sbs_repo.encode('HatEvent', 'Event', event_sbs)


def decode_event(event_bytes: bytes) -> common.Event:
    event_sbs = common.sbs_repo.decode('HatEvent', 'Event', event_bytes)
    return common.event_from_sbs(event_sbs)


def encode_timestamp_id(x: typing.Tuple[common.Timestamp, int]) -> bytes:
    t, instance_id = x
    return struct.pack(">QIQ", t.s + (1 << 63), t.us, instance_id)


def decode_timestamp_id(x: bytes) -> typing.Tuple[common.Timestamp, int]:
    t_s, t_us, instance_id = struct.unpack(">QIQ", x)
    return common.Timestamp(t_s - (1 << 63), t_us), instance_id


def encode_str(x: str) -> bytes:
    return bytes(x, encoding='utf-8')


def decode_str(x: bytes) -> str:
    return str(x, encoding='utf-8')


def encode_json(x: json.Data) -> bytes:
    return encode_str(json.encode(x))


def decode_json(x: bytes) -> json.Data:
    return json.decode(decode_str(x))


def encode_system_data(data: common.SystemData) -> bytes:
    last_timestamp = list(data.last_timestamp) if data.last_timestamp else None
    return encode_json({'server_id': data.server_id,
                        'last_instance_id': data.last_instance_id,
                        'last_timestamp': last_timestamp})


def decode_system_data(data_bytes: bytes) -> common.SystemData:
    data_json = decode_json(data_bytes)
    last_timestamp = (common.Timestamp(*data_json['last_timestamp'])
                      if data_json['last_timestamp'] else None)
    return common.SystemData(server_id=data_json['server_id'],
                             last_instance_id=data_json['last_instance_id'],
                             last_timestamp=last_timestamp)


def encode_tuple_str(x: typing.Tuple[str, ...]) -> bytes:
    return encode_str(json.encode(list(x)))


def decode_tuple_str(x: bytes) -> typing.Tuple[str, ...]:
    return tuple(json.decode(decode_str(x)))
