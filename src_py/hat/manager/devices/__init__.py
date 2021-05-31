"""Device implementations"""

from hat import json
from hat.manager import common
import hat.manager.devices.event
import hat.manager.devices.iec104
import hat.manager.devices.modbus
import hat.manager.devices.monitor
import hat.manager.devices.orchestrator


def get_default_conf(device_type: str) -> json.Data:
    """Get default configuration associated with provided device type"""

    if device_type == 'orchestrator':
        return hat.manager.devices.orchestrator.default_conf

    if device_type == 'monitor':
        return hat.manager.devices.monitor.default_conf

    if device_type == 'event':
        return hat.manager.devices.event.default_conf

    if device_type == 'iec104_master':
        return hat.manager.devices.iec104.default_master_conf

    if device_type == 'iec104_slave':
        return hat.manager.devices.iec104.default_slave_conf

    if device_type == 'modbus_master':
        return hat.manager.devices.modbus.default_master_conf

    if device_type == 'modbus_slave':
        return hat.manager.devices.modbus.default_slave_conf

    raise ValueError('unsupported device type')


def create_device(conf: json.Data,
                  logger: common.Logger
                  ) -> common.Device:
    """Create device instance

    Args:
        conf: configuration defined by
            ``hat://manager/main.yaml#/definitions/device``
        logger: device logger

    Returns:
        device instance

    """
    device_type = conf['type']

    if device_type == 'orchestrator':
        return hat.manager.devices.orchestrator.Device(conf, logger)

    if device_type == 'monitor':
        return hat.manager.devices.monitor.Device(conf, logger)

    if device_type == 'event':
        return hat.manager.devices.event.Device(conf, logger)

    if device_type == 'iec104_master':
        return hat.manager.devices.iec104.Master(conf, logger)

    if device_type == 'iec104_slave':
        return hat.manager.devices.iec104.Slave(conf, logger)

    if device_type == 'modbus_master':
        return hat.manager.devices.modbus.Master(conf, logger)

    if device_type == 'modbus_slave':
        return hat.manager.devices.modbus.Slave(conf, logger)

    raise ValueError('unsupported device type')
