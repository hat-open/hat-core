import collections
import functools
import itertools
import math
import typing

from hat import util
from hat.asn1 import common


syntax_name = [('joint-iso-itu-t', 2),
               ('asn1', 1),
               ('basic-encoding', 1)]


class PrimitiveContent(typing.NamedTuple):
    value: common.Data


class ConstructedContent(typing.NamedTuple):
    elements: typing.List['Entity']


class Entity(typing.NamedTuple):
    class_type: common.ClassType
    tag_number: int
    content: typing.Union[PrimitiveContent, ConstructedContent]


common.Entity.register(Entity)


def encode_value(refs: typing.Dict[common.TypeRef, common.Type],
                 t: common.Type,
                 value: common.Value
                 ) -> Entity:
    """Encode value to entity"""
    while isinstance(t, common.TypeRef):
        t = refs[t]

    if isinstance(t, common.BooleanType):
        return Entity(common.ClassType.UNIVERSAL, 1,
                      _encode_boolean(value))

    if isinstance(t, common.IntegerType):
        return Entity(common.ClassType.UNIVERSAL, 2,
                      _encode_integer(value))

    if isinstance(t, common.BitStringType):
        return Entity(common.ClassType.UNIVERSAL, 3,
                      _encode_bitstring(value))

    if isinstance(t, common.OctetStringType):
        return Entity(common.ClassType.UNIVERSAL, 4,
                      _encode_octetstring(value))

    if isinstance(t, common.NullType):
        return Entity(common.ClassType.UNIVERSAL, 5,
                      _encode_null())

    if isinstance(t, common.ObjectIdentifierType):
        return Entity(common.ClassType.UNIVERSAL, 6,
                      _encode_objectidentifier(value))

    if isinstance(t, common.StringType):
        return Entity(common.ClassType.UNIVERSAL, t.value,
                      _encode_string(value))

    if isinstance(t, common.ExternalType):
        return Entity(common.ClassType.UNIVERSAL, 8,
                      _encode_external(value))

    if isinstance(t, common.RealType):
        return Entity(common.ClassType.UNIVERSAL, 9,
                      _encode_real(value))

    if isinstance(t, common.EnumeratedType):
        return Entity(common.ClassType.UNIVERSAL, 10,
                      _encode_integer(value))

    if isinstance(t, common.EmbeddedPDVType):
        return Entity(common.ClassType.UNIVERSAL, 11,
                      _encode_embeddedpdv(value))

    if isinstance(t, common.ChoiceType):
        name, subvalue = value
        prop = util.first(t.choices, lambda x: x.name == name)
        return encode_value(refs, prop.type, subvalue)

    if isinstance(t, common.SetType):
        return Entity(common.ClassType.UNIVERSAL, 17,
                      ConstructedContent(list(
                        _encode_elements(refs, t.elements, value))))

    if isinstance(t, common.SetOfType):
        return Entity(common.ClassType.UNIVERSAL, 17,
                      ConstructedContent([encode_value(refs, t.type, i)
                                          for i in value]))

    if isinstance(t, common.SequenceType):
        return Entity(common.ClassType.UNIVERSAL, 16,
                      ConstructedContent(list(
                        _encode_elements(refs, t.elements, value))))

    if isinstance(t, common.SequenceOfType):
        return Entity(common.ClassType.UNIVERSAL, 16,
                      ConstructedContent([encode_value(refs, t.type, i)
                                          for i in value]))

    if isinstance(t, common.EntityType):
        return value

    if isinstance(t, common.UnsupportedType):
        raise NotImplementedError()

    if isinstance(t, common.PrefixedType):
        entity = encode_value(refs, t.type, value)
        if t.implicit:
            entity = entity._replace(class_type=t.class_type,
                                     tag_number=t.tag_number)
        else:
            entity = Entity(t.class_type, t.tag_number,
                            ConstructedContent([entity]))
        return entity

    raise ValueError('invalid type definition')


def decode_value(refs: typing.Dict[common.TypeRef, common.Type],
                 t: common.Type,
                 entity: Entity
                 ) -> common.Value:
    """Decode value from entity"""
    while isinstance(t, common.TypeRef):
        t = refs[t]

    if isinstance(t, common.BooleanType):
        return _decode_boolean(entity.content)

    if isinstance(t, common.IntegerType):
        return _decode_integer(entity.content)

    if isinstance(t, common.BitStringType):
        return _decode_bitstring(entity.content)

    if isinstance(t, common.OctetStringType):
        return _decode_octetstring(entity.content)

    if isinstance(t, common.NullType):
        return

    if isinstance(t, common.ObjectIdentifierType):
        return _decode_objectidentifier(entity.content)

    if isinstance(t, common.StringType):
        return _decode_string(entity.content)

    if isinstance(t, common.ExternalType):
        return _decode_external(entity.content)

    if isinstance(t, common.RealType):
        return _decode_real(entity.content)

    if isinstance(t, common.EnumeratedType):
        return _decode_integer(entity.content)

    if isinstance(t, common.EmbeddedPDVType):
        return _decode_embeddedpdv(entity.content)

    if isinstance(t, common.ChoiceType):
        for prop in t.choices:
            if _match_type_entity(refs, prop.type, entity):
                return prop.name, decode_value(refs, prop.type, entity)
        raise ValueError('invalid choice')

    if isinstance(t, common.SetType):
        value = {}
        elements = list(entity.content.elements)
        for prop in t.elements:
            match = functools.partial(_match_type_entity, refs, prop.type)
            subentity = util.first(elements,  match)
            if not subentity:
                if prop.optional:
                    continue
                raise ValueError(f'missing property {prop.name}')
            value[prop.name] = decode_value(refs, prop.type, subentity)
            elements.remove(subentity)
        return value

    if isinstance(t, common.SetOfType):
        return [decode_value(refs, t.type, i) for i in entity.content.elements]

    if isinstance(t, common.SequenceType):
        value = {}
        elements = collections.deque(entity.content.elements)
        for prop in t.elements:
            if elements and _match_type_entity(refs, prop.type, elements[0]):
                value[prop.name] = decode_value(refs, prop.type,
                                                elements.popleft())
            elif not prop.optional:
                raise ValueError(f'missing property {prop.name}')
        return value

    if isinstance(t, common.SequenceOfType):
        return [decode_value(refs, t.type, i) for i in entity.content.elements]

    if isinstance(t, common.EntityType):
        return entity

    if isinstance(t, common.UnsupportedType):
        raise NotImplementedError()

    if isinstance(t, common.PrefixedType):
        return decode_value(refs, t.type,
                            entity if t.implicit
                            else entity.content.elements[0])

    raise ValueError('invalid type definition')


def encode_entity(entity: Entity) -> common.Data:
    """Encode entity"""
    is_primitive = isinstance(entity.content, PrimitiveContent)
    is_constructed = isinstance(entity.content, ConstructedContent)
    entity_bytes = []

    next_byte = 0
    next_byte |= (entity.class_type.value << 6)
    next_byte |= (is_constructed << 5)
    if entity.tag_number <= 30:
        next_byte |= entity.tag_number
        entity_bytes.append(next_byte)
    else:
        next_byte |= 0x1F
        entity_bytes.append(next_byte)
        tag_number = entity.tag_number
        next_bytes = [tag_number & 0x7F]
        tag_number >>= 7
        while tag_number > 0:
            next_byte = tag_number & 0x7F
            next_bytes.insert(0, 0x80 | next_byte)
            tag_number >>= 7
        entity_bytes.extend(next_bytes)

    if is_primitive:
        length = len(entity.content.value)
        entity_bytes.extend(_encode_entity_length(length))
        entity_bytes.extend(entity.content.value)
    elif is_constructed:
        length = 0
        next_bytes = []
        for entity in entity.content.elements:
            subentity_bytes = encode_entity(entity)
            length += len(subentity_bytes)
            next_bytes.extend(subentity_bytes)
        entity_bytes.extend(_encode_entity_length(length))
        entity_bytes.extend(next_bytes)
    else:
        raise ValueError('invalid entity content')

    return bytes(entity_bytes)


def decode_entity(data: common.Data) -> typing.Tuple[Entity, common.Data]:
    """Decode entity

    Returns entity and remaining data.

    """
    class_type = common.ClassType(data[0] >> 6)
    is_constructed = bool(data[0] & 0x20)
    tag_number = data[0] & 0x1F

    if tag_number == 0x1F:
        tag_number = 0
        data = data[1:]
        while True:
            tag_number = (tag_number << 7) | (data[0] & 0x7F)
            if not (data[0] & 0x80):
                break
            data = data[1:]

    data = data[1:]
    length = data[0]
    data = data[1:]

    if length == 0x80:
        if not is_constructed:
            raise ValueError('invalid primitive content length')
        content = ConstructedContent([])
        while data[:2] != b'\x00\x00':
            subentity, data = decode_entity(data)
            content.elements.append(subentity)
        data = data[2:]
        entity = Entity(class_type, tag_number, content)
        return entity, data

    if length & 0x80:
        length, data = (
            int.from_bytes(data[:(length & 0x7F)], 'big'),
            data[(length & 0x7F):])

    content_bytes = data[:length]
    data = data[length:]

    if is_constructed:
        content = ConstructedContent([])
        while content_bytes:
            subentity, content_bytes = decode_entity(content_bytes)
            content.elements.append(subentity)
    else:
        content = PrimitiveContent(content_bytes)

    entity = Entity(class_type, tag_number, content)
    return entity, data


def _encode_elements(refs, props, value):
    for prop in props:
        if prop.optional and prop.name not in value:
            continue
        yield encode_value(refs, prop.type, value[prop.name])


def _encode_boolean(value):
    return PrimitiveContent(bytes([0x01 if value else 0x00]))


def _decode_boolean(content):
    return bool(content.value[0])


def _encode_integer(value):
    return PrimitiveContent(value.to_bytes((value.bit_length() // 8) + 1,
                                           byteorder='big',
                                           signed=value < 0))


def _decode_integer(content):
    return int.from_bytes(content.value,
                          byteorder='big',
                          signed=bool(content.value[0] & 0x80))


def _encode_bitstring(value):
    unused_bits = (8 - len(value) % 8) % 8
    content_bytes = [unused_bits]
    for i, bit in enumerate(value):
        if i % 8 == 0:
            content_bytes.append(0)
        if bit:
            content_bytes[-1] |= (1 << (7 - i % 8))
    return PrimitiveContent(bytes(content_bytes))


def _decode_bitstring(content):
    if isinstance(content, PrimitiveContent):
        unused_bits = content.value[0]
        value = content.value[1:]
        bitstring = []
        for byte in value:
            for i in range(8):
                if (byte << i) & 0x80:
                    bitstring.append(True)
                else:
                    bitstring.append(False)
        if unused_bits:
            bitstring = bitstring[:-unused_bits]
        return bitstring

    if isinstance(content, ConstructedContent):
        bitstring = []
        for subentity in content.elements:
            bitstring.extend(_decode_bitstring(subentity.content))
        return bitstring

    raise ValueError('invalid entity content')


def _encode_octetstring(value):
    return PrimitiveContent(value)


def _decode_octetstring(content):
    if isinstance(content, PrimitiveContent):
        return content.value

    if isinstance(content, ConstructedContent):
        return bytes(itertools.chain.from_iterable(
            _decode_octetstring(i.content) for i in content.elements))

    raise ValueError('invalid entity content')


def _encode_null():
    return PrimitiveContent(b'')


def _encode_objectidentifier(value):
    value = [i if isinstance(i, int) else i[1] for i in value]
    if len(value) < 2:
        raise ValueError('invalid object identifier')
    if value[0] > 2:
        raise ValueError('invalid object identifier')
    if value[0] < 2 and value[1] > 39:
        raise ValueError('invalid object identifier')
    value = [40 * value[0] + value[1], *value[2:]]
    content_bytes = []
    for id in value:
        id_bytes = collections.deque()
        while id:
            id_bytes.appendleft(0x80 | (id & 0x7F))
            id >>= 7
        if not id_bytes:
            id_bytes.appendleft(0)
        else:
            id_bytes.append(id_bytes.pop() & 0x7F)
        content_bytes.extend(id_bytes)
    return PrimitiveContent(bytes(content_bytes))


def _decode_objectidentifier(content):
    if len(content.value) < 1:
        raise ValueError('invalid object identifier')
    ids = []
    next_id = 0
    for byte in content.value:
        next_id <<= 7
        next_id |= (byte & 0x7F)
        if not (byte & 0x80):
            ids.append(next_id)
            next_id = 0
    if len(ids) < 1:
        raise ValueError('invalid object identifier')
    first_id = min(ids[0] // 40, 2)
    second_id = ids[0] % 40 if first_id < 2 else ids[0] - 2 * 40
    ids = [first_id, second_id, *ids[1:]]
    return ids


def _encode_string(value):
    return PrimitiveContent(value.encode('utf-8'))


def _decode_string(content):
    if isinstance(content, PrimitiveContent):
        return str(content.value, encoding='utf-8')

    if isinstance(content, ConstructedContent):
        return ''.join(_decode_string(i.content) for i in content.elements)

    raise ValueError('invalid entity content')


def _encode_external(value):
    elements = []

    if value.direct_ref is not None:
        entity = Entity(common.ClassType.UNIVERSAL, 6,
                        _encode_objectidentifier(value.direct_ref))
        elements.append(entity)

    if value.indirect_ref is not None:
        entity = Entity(common.ClassType.UNIVERSAL, 2,
                        _encode_integer(value.indirect_ref))
        elements.append(entity)

    if isinstance(value.data, Entity):
        entity = Entity(common.ClassType.CONTEXT_SPECIFIC, 0,
                        ConstructedContent([value.data]))
    elif _is_data(value.data):
        entity = Entity(common.ClassType.CONTEXT_SPECIFIC, 1,
                        _encode_octetstring(value.data))
    else:
        entity = Entity(common.ClassType.CONTEXT_SPECIFIC, 2,
                        _encode_bitstring(value.data))
    elements.append(entity)

    return ConstructedContent(elements)


def _decode_external(content):
    entity = util.first(content.elements, lambda x: (
        x.class_type == common.ClassType.UNIVERSAL and
        x.tag_number == 6))
    direct_ref = _decode_objectidentifier(entity.content) if entity else None

    entity = util.first(content.elements, lambda x: (
        x.class_type == common.ClassType.UNIVERSAL and
        x.tag_number == 2))
    indirect_ref = _decode_integer(entity.content) if entity else None

    entity = content.elements[-1]
    if entity.tag_number == 0:
        data = entity.content.elements[0]
    elif entity.tag_number == 1:
        data = _decode_octetstring(entity.content)
    elif entity.tag_number == 2:
        data = _decode_bitstring(entity.content)
    else:
        raise ValueError('invalid external content')

    return common.External(data=data,
                           direct_ref=direct_ref,
                           indirect_ref=indirect_ref)


def _encode_real(value):
    raise NotImplementedError()


def _decode_real(content):
    raise NotImplementedError()


def _encode_embeddedpdv(value):
    if value.abstract is not None:
        if isinstance(value.abstract, int):
            abstract_entity = Entity(common.ClassType.UNIVERSAL, 2,
                                     _encode_integer(value.abstract))
        elif value.transfer is not None:
            abstract_entity = Entity(common.ClassType.UNIVERSAL, 6,
                                     _encode_objectidentifier(value.abstract))
        else:
            raise ValueError()

    if value.transfer is not None:
        transfer_entity = Entity(common.ClassType.UNIVERSAL, 6,
                                 _encode_objectidentifier(value.transfer))

    if value.abstract is None and value.transfer is None:
        identification_entity = Entity(common.ClassType.UNIVERSAL, 5,
                                       _encode_null())
    elif value.abstract is None:
        identification_entity = transfer_entity
    elif value.transfer is None:
        identification_entity = abstract_entity
    else:
        identification_entity = Entity(
            common.ClassType.UNIVERSAL, 16, ConstructedContent([
                abstract_entity, transfer_entity]))

    data_entity = Entity(common.ClassType.UNIVERSAL, 4,
                         _encode_octetstring(value.data))

    return ConstructedContent([identification_entity, data_entity])


def _decode_embeddedpdv(content):
    identification_entity = content.elements[0]
    data_entity = content.elements[-1]

    if isinstance(identification_entity.content, ConstructedContent):
        abstract_entity = identification_entity.content.elements[0]
        transfer_entity = identification_entity.content.elements[1]
        if abstract_entity.tag_number == 6:
            abstract = _decode_objectidentifier(abstract_entity.content)
        elif abstract_entity.tag_number == 2:
            abstract = _decode_integer(abstract_entity.content)
        else:
            raise ValueError('invalid content')
        if transfer_entity.tag_number != 6:
            raise ValueError('invalid content')
        transfer = _decode_objectidentifier(transfer_entity.content)

    else:
        if identification_entity.tag_number == 6:
            abstract = None
            transfer = _decode_objectidentifier(identification_entity.content)
        elif identification_entity.tag_number == 2:
            abstract = _decode_integer(identification_entity.content)
            transfer = None
        elif identification_entity.tag_number == 5:
            abstract = None
            transfer = None
        else:
            raise ValueError('invalid content')

    if data_entity.tag_number != 4:
        raise ValueError('invalid content')
    data = _decode_octetstring(data_entity.content)

    return common.EmbeddedPDV(abstract=abstract,
                              transfer=transfer,
                              data=data)


def _encode_entity_length(length):
    length_bytes = []
    if length <= 127:
        length_bytes.append(length)
    else:
        next_bytes = _uint_to_bebytes(length)
        if len(next_bytes) > 0x7E:
            raise ValueError('invalid length')
        next_byte = 0x80 | len(next_bytes)
        length_bytes.insert(0, next_byte)
        length_bytes.extend(next_bytes)
    return bytes(length_bytes)


def _match_type_entity(refs, t, entity):
    while isinstance(t, common.TypeRef):
        t = refs[t]

    if isinstance(t, common.BooleanType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 1)

    if isinstance(t, common.IntegerType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 2)

    if isinstance(t, common.BitStringType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 3)

    if isinstance(t, common.OctetStringType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 4)

    if isinstance(t, common.NullType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 5)

    if isinstance(t, common.ObjectIdentifierType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 6)

    if isinstance(t, common.StringType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == t.value)

    if isinstance(t, common.ExternalType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 8)

    if isinstance(t, common.RealType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 9)

    if isinstance(t, common.EnumeratedType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 10)

    if isinstance(t, common.EmbeddedPDVType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 11)

    if isinstance(t, common.ChoiceType):
        return any(_match_type_entity(refs, i.type, entity)
                   for i in t.choices)

    if isinstance(t, common.SetType) or isinstance(t, common.SetOfType):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 17)

    if (isinstance(t, common.SequenceType) or
            isinstance(t, common.SequenceOfType)):
        return (entity.class_type == common.ClassType.UNIVERSAL and
                entity.tag_number == 16)

    if isinstance(t, common.EntityType):
        return True

    if isinstance(t, common.UnsupportedType):
        raise NotImplementedError()

    if isinstance(t, common.PrefixedType):
        return (entity.class_type == t.class_type and
                entity.tag_number == t.tag_number)

    raise ValueError('invalid type definition')


def _uint_to_bebytes(x):
    bytes_len = max(math.ceil(x.bit_length() / 8), 1)
    return x.to_bytes(bytes_len, 'big')


def _is_data(x):
    return any(isinstance(x, i) for i in typing.get_args(common.Data))
