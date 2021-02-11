import enum
import typing

from hat.drivers.iec104.common import (Cause,
                                       Time,
                                       SingleValue,
                                       DoubleValue,
                                       StepPositionValue,
                                       BitstringValue,
                                       NormalizedValue,
                                       ScaledValue,
                                       FloatingValue,
                                       BinaryCounterValue,
                                       RegulatingValue,
                                       FreezeCode,
                                       Quality)
from hat.drivers.iec104.common import *  # NOQA


class ApduFunction(enum.Enum):
    TESTFR_CON = 0x83
    TESTFR_ACT = 0x43
    STOPDT_CON = 0x23
    STOPDT_ACT = 0x13
    STARTDT_CON = 0x0B
    STARTDT_ACT = 0x07


class AsduType(enum.Enum):
    M_SP_NA = 1
    M_DP_NA = 3
    M_ST_NA = 5
    M_BO_NA = 7
    M_ME_NA = 9
    M_ME_NB = 11
    M_ME_NC = 13
    M_IT_NA = 15
    M_ME_ND = 21
    M_SP_TB = 30
    M_DP_TB = 31
    M_ST_TB = 32
    M_BO_TB = 33
    M_ME_TD = 34
    M_ME_TE = 35
    M_ME_TF = 36
    M_IT_TB = 37
    C_SC_NA = 45
    C_DC_NA = 46
    C_RC_NA = 47
    C_SE_NA = 48
    C_SE_NB = 49
    C_SE_NC = 50
    C_SC_TA = 58
    C_DC_TA = 59
    C_RC_TA = 60
    C_SE_TA = 61
    C_SE_TB = 62
    C_SE_TC = 63
    M_EI_NA = 70
    C_IC_NA = 100
    C_CI_NA = 101


class APDUI(typing.NamedTuple):
    ssn: int
    rsn: int
    asdu: typing.Optional['ASDU']


class APDUS(typing.NamedTuple):
    rsn: int


class APDUU(typing.NamedTuple):
    function: ApduFunction


APDU = typing.Union[APDUI, APDUS, APDUU]


class ASDU(typing.NamedTuple):
    type: AsduType
    cause: Cause
    is_negative_confirm: bool
    is_test: bool
    originator_address: typing.Optional[int]
    address: int
    ios: typing.List['IO']


class IO(typing.NamedTuple):
    address: int
    elements: typing.List['IOElement']
    time: typing.Optional[Time]


class IOElement_M_SP_NA(typing.NamedTuple):
    value: SingleValue
    quality: Quality


class IOElement_M_DP_NA(typing.NamedTuple):
    value: DoubleValue
    quality: Quality


class IOElement_M_ST_NA(typing.NamedTuple):
    value: StepPositionValue
    quality: Quality


class IOElement_M_BO_NA(typing.NamedTuple):
    value: BitstringValue
    quality: Quality


class IOElement_M_ME_NA(typing.NamedTuple):
    value: NormalizedValue
    quality: Quality


class IOElement_M_ME_NB(typing.NamedTuple):
    value: ScaledValue
    quality: Quality


class IOElement_M_ME_NC(typing.NamedTuple):
    value: FloatingValue
    quality: Quality


class IOElement_M_IT_NA(typing.NamedTuple):
    value: BinaryCounterValue


class IOElement_M_ME_ND(typing.NamedTuple):
    value: NormalizedValue


class IOElement_M_SP_TB(typing.NamedTuple):
    value: SingleValue
    quality: Quality


class IOElement_M_DP_TB(typing.NamedTuple):
    value: DoubleValue
    quality: Quality


class IOElement_M_ST_TB(typing.NamedTuple):
    value: StepPositionValue
    quality: Quality


class IOElement_M_BO_TB(typing.NamedTuple):
    value: BitstringValue
    quality: Quality


class IOElement_M_ME_TD(typing.NamedTuple):
    value: NormalizedValue
    quality: Quality


class IOElement_M_ME_TE(typing.NamedTuple):
    value: ScaledValue
    quality: Quality


class IOElement_M_ME_TF(typing.NamedTuple):
    value: FloatingValue
    quality: Quality


class IOElement_M_IT_TB(typing.NamedTuple):
    value: BinaryCounterValue


class IOElement_C_SC_NA(typing.NamedTuple):
    value: SingleValue
    select: bool
    qualifier: int


class IOElement_C_DC_NA(typing.NamedTuple):
    value: DoubleValue
    select: bool
    qualifier: int


class IOElement_C_RC_NA(typing.NamedTuple):
    value: RegulatingValue
    select: bool
    qualifier: int


class IOElement_C_SE_NA(typing.NamedTuple):
    value: NormalizedValue
    select: bool
    qualifier: int


class IOElement_C_SE_NB(typing.NamedTuple):
    value: ScaledValue
    select: bool
    qualifier: int


class IOElement_C_SE_NC(typing.NamedTuple):
    value: FloatingValue
    select: bool
    qualifier: int


class IOElement_C_SC_TA(typing.NamedTuple):
    value: SingleValue
    select: bool
    qualifier: int


class IOElement_C_DC_TA(typing.NamedTuple):
    value: DoubleValue
    select: bool
    qualifier: int


class IOElement_C_RC_TA(typing.NamedTuple):
    value: RegulatingValue
    select: bool
    qualifier: int


class IOElement_C_SE_TA(typing.NamedTuple):
    value: NormalizedValue
    select: bool
    qualifier: int


class IOElement_C_SE_TB(typing.NamedTuple):
    value: ScaledValue
    select: bool
    qualifier: int


class IOElement_C_SE_TC(typing.NamedTuple):
    value: FloatingValue
    select: bool
    qualifier: int


class IOElement_M_EI_NA(typing.NamedTuple):
    param_change: bool
    cause: int


class IOElement_C_IC_NA(typing.NamedTuple):
    qualifier: int


class IOElement_C_CI_NA(typing.NamedTuple):
    request: int
    freeze: FreezeCode


IOElement = typing.Union[IOElement_M_SP_NA,
                         IOElement_M_DP_NA,
                         IOElement_M_ST_NA,
                         IOElement_M_BO_NA,
                         IOElement_M_ME_NA,
                         IOElement_M_ME_NB,
                         IOElement_M_ME_NC,
                         IOElement_M_IT_NA,
                         IOElement_M_ME_ND,
                         IOElement_M_SP_TB,
                         IOElement_M_DP_TB,
                         IOElement_M_ST_TB,
                         IOElement_M_BO_TB,
                         IOElement_M_ME_TD,
                         IOElement_M_ME_TE,
                         IOElement_M_ME_TF,
                         IOElement_M_IT_TB,
                         IOElement_C_SC_NA,
                         IOElement_C_DC_NA,
                         IOElement_C_RC_NA,
                         IOElement_C_SE_NA,
                         IOElement_C_SE_NB,
                         IOElement_C_SE_NC,
                         IOElement_C_SC_TA,
                         IOElement_C_DC_TA,
                         IOElement_C_RC_TA,
                         IOElement_C_SE_TA,
                         IOElement_C_SE_TB,
                         IOElement_C_SE_TC,
                         IOElement_M_EI_NA,
                         IOElement_C_IC_NA,
                         IOElement_C_CI_NA]
