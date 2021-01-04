import abc
import enum
import typing
import datetime

from hat import asn1


class DataAccessError(enum.Enum):
    OBJECT_INVALIDATED = 0
    HARDWARE_FAULT = 1
    TEMPORARILY_UNAVAILABLE = 2
    OBJECT_ACCESS_DENIED = 3
    OBJECT_UNDEFINED = 4
    INVALID_ADDRESS = 5
    TYPE_UNSUPPORTED = 6
    TYPE_INCONSISTENT = 7
    OBJECT_ATTRIBUTE_INCONSISTENT = 8
    OBJECT_ACCESS_UNSUPPORTED = 9
    OBJECT_NON_EXISTENT = 10
    OBJECT_VALUE_INVALID = 11


class ObjectClass(enum.Enum):
    NAMED_VARIABLE = 0
    NAMED_VARIABLE_LIST = 2
    JOURNAL = 8
    DOMAIN = 9
    UNDEFINED = 0xFF


class ErrorClass(enum.Enum):
    ACCESS = 'access'
    APPLICATION_REFERENCE = 'application-reference'
    CANCEL = 'cancel'
    CONCLUDE = 'conclude'
    DEFINITION = 'definition'
    FILE = 'file'
    INITIATE = 'initiate'
    OTHERS = 'others'
    RESOURCE = 'resource'
    SERVICE = 'service'
    SERVICE_PREEMPT = 'service-preempt'
    TIME_RESOLUTION = 'time-resolution'
    VMD_STATE = 'vmd-state'


class StatusRequest(typing.NamedTuple):
    pass


class GetNameListRequest(typing.NamedTuple):
    object_class: ObjectClass
    object_scope: 'ObjectScope'
    continue_after: typing.Optional[str]


class IdentifyRequest(typing.NamedTuple):
    pass


class GetVariableAccessAttributesRequest(typing.NamedTuple):
    value: typing.Union['ObjectName', int, str, asn1.Data]


class GetNamedVariableListAttributesRequest(typing.NamedTuple):
    value: 'ObjectName'


class ReadRequest(typing.NamedTuple):
    value: typing.Union[typing.List['VariableSpecification'], 'ObjectName']


class WriteRequest(typing.NamedTuple):
    specification: typing.Union[typing.List['VariableSpecification'],
                                'ObjectName']
    data: typing.List['Data']


class DefineNamedVariableListRequest(typing.NamedTuple):
    name: 'ObjectName'
    specification: typing.List['VariableSpecification']


class DeleteNamedVariableListRequest(typing.NamedTuple):
    names: typing.List['ObjectName']


Request = type('Request', (abc.ABC, ), {})
Request.register(StatusRequest)
Request.register(GetNameListRequest)
Request.register(IdentifyRequest)
Request.register(GetVariableAccessAttributesRequest)
Request.register(GetNamedVariableListAttributesRequest)
Request.register(ReadRequest)
Request.register(WriteRequest)
Request.register(DefineNamedVariableListRequest)
Request.register(DeleteNamedVariableListRequest)


class ErrorResponse(typing.NamedTuple):
    error_class: ErrorClass
    value: int


class StatusResponse(typing.NamedTuple):
    logical: int
    physical: int


class GetNameListResponse(typing.NamedTuple):
    identifiers: typing.List[str]
    more_follows: bool


class IdentifyResponse(typing.NamedTuple):
    vendor: str
    model: str
    revision: str
    syntaxes: typing.Optional[typing.List[asn1.ObjectIdentifier]]


class GetVariableAccessAttributesResponse(typing.NamedTuple):
    mms_deletable: bool
    type_description: 'TypeDescription'


class GetNamedVariableListAttributesResponse(typing.NamedTuple):
    mms_deletable: bool
    specification: typing.List['VariableSpecification']


class ReadResponse(typing.NamedTuple):
    results: typing.List[typing.Union[DataAccessError, 'Data']]


class WriteResponse(typing.NamedTuple):
    results: typing.List[typing.Optional[DataAccessError]]


class DefineNamedVariableListResponse(typing.NamedTuple):
    pass


class DeleteNamedVariableListResponse(typing.NamedTuple):
    matched: int
    deleted: int


Response = type('Response', (abc.ABC, ), {})
Response.register(ErrorResponse)
Response.register(StatusResponse)
Response.register(GetNameListResponse)
Response.register(IdentifyResponse)
Response.register(GetVariableAccessAttributesResponse)
Response.register(GetNamedVariableListAttributesResponse)
Response.register(ReadResponse)
Response.register(WriteResponse)
Response.register(DefineNamedVariableListResponse)
Response.register(DeleteNamedVariableListResponse)


class EventNotificationUnconfirmed(typing.NamedTuple):
    enrollment: 'ObjectName'
    condition: 'ObjectName'
    severity: int
    time: typing.Optional[typing.Union['Data', int]]


class InformationReportUnconfirmed(typing.NamedTuple):
    specification: typing.Union[typing.List['VariableSpecification'],
                                'ObjectName']
    data: typing.List[typing.Union[DataAccessError, 'Data']]


class UnsolicitedStatusUnconfirmed(typing.NamedTuple):
    logical: int
    physical: int


Unconfirmed = type('Unconfirmed', (abc.ABC, ), {})
Unconfirmed.register(EventNotificationUnconfirmed)
Unconfirmed.register(InformationReportUnconfirmed)
Unconfirmed.register(UnsolicitedStatusUnconfirmed)


class ArrayData(typing.NamedTuple):
    elements: typing.List['Data']


class BcdData(typing.NamedTuple):
    value: int


class BinaryTimeData(typing.NamedTuple):
    value: datetime.datetime


class BitStringData(typing.NamedTuple):
    value: typing.List[bool]


class BooleanData(typing.NamedTuple):
    value: bool


class BooleanArrayData(typing.NamedTuple):
    value: typing.List[bool]


class FloatingPointData(typing.NamedTuple):
    value: float


class GeneralizedTimeData(typing.NamedTuple):
    value: str


class IntegerData(typing.NamedTuple):
    value: int


class MmsStringData(typing.NamedTuple):
    value: str


class ObjIdData(typing.NamedTuple):
    value: asn1.ObjectIdentifier


class OctetStringData(typing.NamedTuple):
    value: asn1.Data


class StructureData(typing.NamedTuple):
    elements: typing.List['Data']


class UnsignedData(typing.NamedTuple):
    value: int


class UtcTimeData(typing.NamedTuple):
    value: datetime.datetime
    leap_second: bool
    clock_failure: bool
    not_synchronized: bool
    accuracy: typing.Optional[int]
    """accurate fraction bits [0,24]"""


class VisibleStringData(typing.NamedTuple):
    value: str


Data = type('Data', (abc.ABC, ), {})
Data.register(ArrayData)
Data.register(BcdData)
Data.register(BinaryTimeData)
Data.register(BitStringData)
Data.register(BooleanData)
Data.register(BooleanArrayData)
Data.register(FloatingPointData)
Data.register(GeneralizedTimeData)
Data.register(IntegerData)
Data.register(MmsStringData)
Data.register(ObjIdData)
Data.register(OctetStringData)
Data.register(StructureData)
Data.register(UnsignedData)
Data.register(UtcTimeData)
Data.register(VisibleStringData)


class ArrayTypeDescription(typing.NamedTuple):
    number_of_elements: int
    element_type: typing.Union['TypeDescription', 'ObjectName']


class BcdTypeDescription(typing.NamedTuple):
    xyz: int


class BinaryTimeTypeDescription(typing.NamedTuple):
    xyz: bool


class BitStringTypeDescription(typing.NamedTuple):
    xyz: int


class BooleanTypeDescription(typing.NamedTuple):
    pass


class FloatingPointTypeDescription(typing.NamedTuple):
    format_width: int
    exponent_width: int


class GeneralizedTimeTypeDescription(typing.NamedTuple):
    pass


class IntegerTypeDescription(typing.NamedTuple):
    xyz: int


class MmsStringTypeDescription(typing.NamedTuple):
    xyz: int


class ObjIdTypeDescription(typing.NamedTuple):
    pass


class OctetStringTypeDescription(typing.NamedTuple):
    xyz: int


class StructureTypeDescription(typing.NamedTuple):
    components: typing.List[typing.Tuple[typing.Optional[str],
                                         typing.Union['TypeDescription',
                                                      'ObjectName']]]


class UnsignedTypeDescription(typing.NamedTuple):
    xyz: int


class UtcTimeTypeDescription(typing.NamedTuple):
    pass


class VisibleStringTypeDescription(typing.NamedTuple):
    xyz: int


TypeDescription = type('TypeDescription', (abc.ABC, ), {})
TypeDescription.register(ArrayTypeDescription)
TypeDescription.register(BcdTypeDescription)
TypeDescription.register(BinaryTimeTypeDescription)
TypeDescription.register(BitStringTypeDescription)
TypeDescription.register(BooleanTypeDescription)
TypeDescription.register(FloatingPointTypeDescription)
TypeDescription.register(GeneralizedTimeTypeDescription)
TypeDescription.register(IntegerTypeDescription)
TypeDescription.register(MmsStringTypeDescription)
TypeDescription.register(ObjIdTypeDescription)
TypeDescription.register(OctetStringTypeDescription)
TypeDescription.register(StructureTypeDescription)
TypeDescription.register(UnsignedTypeDescription)
TypeDescription.register(UtcTimeTypeDescription)
TypeDescription.register(VisibleStringTypeDescription)


class AaSpecificObjectName(typing.NamedTuple):
    identifier: str


class DomainSpecificObjectName(typing.NamedTuple):
    domain_id: str
    item_id: str


class VmdSpecificObjectName(typing.NamedTuple):
    identifier: str


ObjectName = type('ObjectName', (abc.ABC, ), {})
ObjectName.register(AaSpecificObjectName)
ObjectName.register(DomainSpecificObjectName)
ObjectName.register(VmdSpecificObjectName)


class AaSpecificObjectScope(typing.NamedTuple):
    pass


class DomainSpecificObjectScope(typing.NamedTuple):
    identifier: str


class VmdSpecificObjectScope(typing.NamedTuple):
    pass


ObjectScope = type('ObjectScope', (abc.ABC, ), {})
ObjectScope.register(AaSpecificObjectScope)
ObjectScope.register(DomainSpecificObjectScope)
ObjectScope.register(VmdSpecificObjectScope)


class AddressVariableSpecification(typing.NamedTuple):
    address: typing.Union[int, str, asn1.Data]


class InvalidatedVariableSpecification(typing.NamedTuple):
    pass


class NameVariableSpecification(typing.NamedTuple):
    name: ObjectName


class ScatteredAccessDescriptionVariableSpecification(typing.NamedTuple):
    specifications: typing.List['VariableSpecification']


class VariableDescriptionVariableSpecification(typing.NamedTuple):
    address: typing.Union[int, str, asn1.Data]
    type_specification: typing.Union[TypeDescription, ObjectName]


VariableSpecification = type('VariableSpecification', (abc.ABC, ), {})
VariableSpecification.register(AddressVariableSpecification)
VariableSpecification.register(InvalidatedVariableSpecification)
VariableSpecification.register(NameVariableSpecification)
VariableSpecification.register(ScatteredAccessDescriptionVariableSpecification)
VariableSpecification.register(VariableDescriptionVariableSpecification)
