# pysqlite2/dbapi2.py: the DB-API 2.0 interface
#
# Copyright (C) 2004-2005 Gerhard Häring <gh@ghaering.de>
#
# This file is part of pysqlite.
#
# This software is provided 'as-is', without any express or implied
# warranty.  In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.

import datetime
import time
import collections.abc

# HAT modification
from hat._sqlite3 import *  # NOQA

paramstyle = "qmark"

threadsafety = 1

apilevel = "2.0"

Date = datetime.date

Time = datetime.time

Timestamp = datetime.datetime


def DateFromTicks(ticks):
    return Date(*time.localtime(ticks)[:3])


def TimeFromTicks(ticks):
    return Time(*time.localtime(ticks)[3:6])


def TimestampFromTicks(ticks):
    return Timestamp(*time.localtime(ticks)[:6])


version_info = tuple([int(x) for x in version.split(".")])  # NOQA
sqlite_version_info = tuple([int(x) for x in sqlite_version.split(".")])  # NOQA

Binary = memoryview
collections.abc.Sequence.register(Row)  # NOQA


def register_adapters_and_converters():
    def adapt_date(val):
        return val.isoformat()

    def adapt_datetime(val):
        return val.isoformat(" ")

    def convert_date(val):
        return datetime.date(*map(int, val.split(b"-")))

    # def convert_timestamp(val):
    #     datepart, timepart = val.split(b" ")
    #     year, month, day = map(int, datepart.split(b"-"))
    #     timepart_full = timepart.split(b".")
    #     hours, minutes, seconds = map(int, timepart_full[0].split(b":"))
    #     if len(timepart_full) == 2:
    #         microseconds = int('{:0<6.6}'.format(timepart_full[1].decode()))
    #     else:
    #         microseconds = 0
    #
    #     val = datetime.datetime(year, month, day, hours, minutes, seconds,
    #                             microseconds)
    #     return val

    # ###################### HAT modification start ###########################
    def convert_timestamp(val):
        datepart, timetzpart = val.split(b" ")
        if b"+" in timetzpart:
            tzsign = 1
            timepart, tzpart = timetzpart.split(b"+")
        elif b"-" in timetzpart:
            tzsign = -1
            timepart, tzpart = timetzpart.split(b"-")
        else:
            timepart, tzpart = timetzpart, None
        year, month, day = map(int, datepart.split(b"-"))
        timepart_full = timepart.split(b".")
        hours, minutes, seconds = map(int, timepart_full[0].split(b":"))
        if len(timepart_full) == 2:
            microseconds = int('{:0<6.6}'.format(timepart_full[1].decode()))
        else:
            microseconds = 0
        if tzpart:
            tzhours, tzminutes = map(int, tzpart.split(b":"))
            tz = datetime.timezone(
                tzsign * datetime.timedelta(hours=tzhours, minutes=tzminutes))
        else:
            tz = None

        val = datetime.datetime(year, month, day, hours, minutes, seconds,
                                microseconds, tz)
        return val
    # ####################### HAT modification stop ###########################

    register_adapter(datetime.date, adapt_date)  # NOQA
    register_adapter(datetime.datetime, adapt_datetime)  # NOQA
    register_converter("date", convert_date)  # NOQA
    register_converter("timestamp", convert_timestamp)  # NOQA


register_adapters_and_converters()

# Clean up namespace

del(register_adapters_and_converters)
