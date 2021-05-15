"""Modbus master device"""

from hat import json
from hat.gateway import common
from hat.gateway.devices.modbus.master import device


device_type: str = "modbus_master"

json_schema_id: str = "hat://gateway/modbus.yaml#/definitions/master"

json_schema_repo: json.SchemaRepository = common.json_schema_repo

create: common.CreateDevice = device.create
