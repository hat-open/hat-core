import abc
import enum

from hat import util


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


StatusRequest = util.namedtuple('StatusRequest')


GetNameListRequest = util.namedtuple(
    'GetNameListRequest',
    ['object_class', 'ObjectClass'],
    ['object_scope', 'ObjectScope'],
    ['continue_after', 'Optional[str]'])


IdentifyRequest = util.namedtuple('IdentifyRequest')


GetVariableAccessAttributesRequest = util.namedtuple(
    'GetVariableAccessAttributesRequest',
    ['value', 'Union[ObjectName,int,str,hat.asn1.Data]'])


GetNamedVariableListAttributesRequest = util.namedtuple(
    'GetNamedVariableListAttributesRequest',
    ['value', 'ObjectName'])


ReadRequest = util.namedtuple(
    'ReadRequest',
    ['value', 'Union[List[VariableSpecification],ObjectName]'])


WriteRequest = util.namedtuple(
    'WriteRequest',
    ['specification', 'Union[List[VariableSpecification],ObjectName]'],
    ['data', 'List[Data]'])


DefineNamedVariableListRequest = util.namedtuple(
    'DefineNamedVariableListRequest',
    ['name', 'ObjectName'],
    ['specification', 'List[VariableSpecification]'])


DeleteNamedVariableListRequest = util.namedtuple(
    'DeleteNamedVariableListRequest',
    ['names', 'List[ObjectName]'])


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


ErrorResponse = util.namedtuple(
    'ErrorResponse',
    ['error_class', 'ErrorClass'],
    ['value', 'int'])


StatusResponse = util.namedtuple(
    'StatusResponse',
    ['logical', 'int'],
    ['physical', 'int'])


GetNameListResponse = util.namedtuple(
    'GetNameListResponse',
    ['identifiers', 'List[str]'],
    ['more_follows', 'bool'])


IdentifyResponse = util.namedtuple(
    'IdentifyResponse',
    ['vendor', 'str'],
    ['model', 'str'],
    ['revision', 'str'],
    ['syntaxes', 'Optional[List[asn1.ObjectIdentifier]]'])


GetVariableAccessAttributesResponse = util.namedtuple(
    'GetVariableAccessAttributesResponse',
    ['mms_deletable', 'bool'],
    ['type_description', 'TypeDescription'])


GetNamedVariableListAttributesResponse = util.namedtuple(
    'GetNamedVariableListAttributesResponse',
    ['mms_deletable', 'bool'],
    ['specification', 'List[VariableSpecification'])


ReadResponse = util.namedtuple(
    'ReadResponse',
    ['results', 'List[Union[DataAccessError,Data]]'])


WriteResponse = util.namedtuple(
    'WriteResponse',
    ['results', 'List[Optional[DataAccessError]]'])


DefineNamedVariableListResponse = util.namedtuple(
    'DefineNamedVariableListResponse')


DeleteNamedVariableListResponse = util.namedtuple(
    'DeleteNamedVariableListResponse',
    ['matched', 'int'],
    ['deleted', 'int'])


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


EventNotificationUnconfirmed = util.namedtuple(
    'EventNotificationUnconfirmed',
    ['enrollment', 'ObjectName'],
    ['condition', 'ObjectName'],
    ['severity', 'int'],
    ['time', 'Optional[Union[Data,int]]'])


InformationReportUnconfirmed = util.namedtuple(
    'InformationReportUnconfirmed',
    ['specification', 'Union[List[VariableSpecification],ObjectName]'],
    ['data', 'List[Union[DataAccessError,Data]]'])


UnsolicitedStatusUnconfirmed = util.namedtuple(
    'UnsolicitedStatusUnconfirmed',
    ['logical', 'int'],
    ['physical', 'int'])


Unconfirmed = type('Unconfirmed', (abc.ABC, ), {})
Unconfirmed.register(EventNotificationUnconfirmed)
Unconfirmed.register(InformationReportUnconfirmed)
Unconfirmed.register(UnsolicitedStatusUnconfirmed)


ArrayData = util.namedtuple(
    'ArrayData',
    ['elements', 'List[Data]'])


BcdData = util.namedtuple(
    'BcdData',
    ['value', 'int'])


BinaryTimeData = util.namedtuple(
    'BinaryTimeData',
    ['value', 'datetime.datetime'])


BitStringData = util.namedtuple(
    'BitStringData',
    ['value', 'List[bool]'])


BooleanData = util.namedtuple(
    'BooleanData',
    ['value', 'bool'])


BooleanArrayData = util.namedtuple(
    'BooleanArrayData',
    ['value', 'List[bool]'])


FloatingPointData = util.namedtuple(
    'FloatingPointData',
    ['value', 'float'])


GeneralizedTimeData = util.namedtuple(
    'GeneralizedTimeData',
    ['value', 'str'])


IntegerData = util.namedtuple(
    'IntegerData',
    ['value', 'int'])


MmsStringData = util.namedtuple(
    'MmsStringData',
    ['value', 'str'])


ObjIdData = util.namedtuple(
    'ObjIdData',
    ['value', 'asn1.ObjectIdentifier'])


OctetStringData = util.namedtuple(
    'OctetStringData',
    ['value', 'hat.asn1.Data'])


StructureData = util.namedtuple(
    'StructureData',
    ['elements', 'List[Data]'])


UnsignedData = util.namedtuple(
    'UnsignedData',
    ['value', 'int'])


UtcTimeData = util.namedtuple(
    'UtcTimeData',
    ['value', 'datetime.datetime'],
    ['leap_second', 'bool'],
    ['clock_failure', 'bool'],
    ['not_synchronized', 'bool'],
    ['accuracy', 'Optional[int]: accurate fraction bits [0,24]'])


VisibleStringData = util.namedtuple(
    'VisibleStringData',
    ['value', 'str'])


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


ArrayTypeDescription = util.namedtuple(
    'ArrayTypeDescription',
    ['number_of_elements', 'int'],
    ['element_type', 'Union[TypeDescription,ObjectName]'])


BcdTypeDescription = util.namedtuple(
    'BcdTypeDescription',
    ['xyz', 'int'])


BinaryTimeTypeDescription = util.namedtuple(
    'BinaryTimeTypeDescription',
    ['xyz', 'bool'])


BitStringTypeDescription = util.namedtuple(
    'BitStringTypeDescription',
    ['xyz', 'int'])


BooleanTypeDescription = util.namedtuple('BooleanTypeDescription')


FloatingPointTypeDescription = util.namedtuple(
    'FloatingPointTypeDescription',
    ['format_width', 'int'],
    ['exponent_width', 'int'])


GeneralizedTimeTypeDescription = util.namedtuple(
    'GeneralizedTimeTypeDescription')


IntegerTypeDescription = util.namedtuple(
    'IntegerTypeDescription',
    ['xyz', 'int'])


MmsStringTypeDescription = util.namedtuple(
    'MmsStringTypeDescription',
    ['xyz', 'int'])


ObjIdTypeDescription = util.namedtuple('ObjIdTypeDescription')


OctetStringTypeDescription = util.namedtuple(
    'OctetStringTypeDescription',
    ['xyz', 'int'])


StructureTypeDescription = util.namedtuple(
    'StructureTypeDescription',
    ['components', 'List[Tuple[Optional[str],Union[TypeDescription,ObjectName]]]'])  # NOQA


UnsignedTypeDescription = util.namedtuple(
    'UnsignedTypeDescription',
    ['xyz', 'int'])


UtcTimeTypeDescription = util.namedtuple('UtcTimeTypeDescription')


VisibleStringTypeDescription = util.namedtuple(
    'VisibleStringTypeDescription',
    ['xyz', 'int'])


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


AaSpecificObjectName = util.namedtuple(
    'AaSpecificObjectName',
    ['identifier', 'str'])


DomainSpecificObjectName = util.namedtuple(
    'DomainSpecificObjectName',
    ['domain_id', 'str'],
    ['item_id', 'str'])


VmdSpecificObjectName = util.namedtuple(
    'VmdSpecificObjectName',
    ['identifier', 'str'])


ObjectName = type('ObjectName', (abc.ABC, ), {})
ObjectName.register(AaSpecificObjectName)
ObjectName.register(DomainSpecificObjectName)
ObjectName.register(VmdSpecificObjectName)


AaSpecificObjectScope = util.namedtuple('AaSpecificObjectScope')


DomainSpecificObjectScope = util.namedtuple(
    'DomainSpecificObjectScope',
    ['identifier', 'str'])


VmdSpecificObjectScope = util.namedtuple('VmdSpecificObjectScope')


ObjectScope = type('ObjectScope', (abc.ABC, ), {})
ObjectScope.register(AaSpecificObjectScope)
ObjectScope.register(DomainSpecificObjectScope)
ObjectScope.register(VmdSpecificObjectScope)


AddressVariableSpecification = util.namedtuple(
    'AddressVariableSpecification',
    ['address', 'Union[int,str,hat.asn1.Data]'])


InvalidatedVariableSpecification = util.namedtuple(
    'InvalidatedVariableSpecification')


NameVariableSpecification = util.namedtuple(
    'NameVariableSpecification',
    ['name', 'ObjectName'])


ScatteredAccessDescriptionVariableSpecification = util.namedtuple(
    'ScatteredAccessDescriptionVariableSpecification',
    ['specifications', 'List[VariableSpecification]'])


VariableDescriptionVariableSpecification = util.namedtuple(
    'VariableDescriptionVariableSpecification',
    ['address', 'Union[int,str,hat.asn1.Data]'],
    ['type_specification', 'Union[TypeDescription,ObjectName]'])


VariableSpecification = type('VariableSpecification', (abc.ABC, ), {})
VariableSpecification.register(AddressVariableSpecification)
VariableSpecification.register(InvalidatedVariableSpecification)
VariableSpecification.register(NameVariableSpecification)
VariableSpecification.register(ScatteredAccessDescriptionVariableSpecification)
VariableSpecification.register(VariableDescriptionVariableSpecification)
