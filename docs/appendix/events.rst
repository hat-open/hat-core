Event definitions
=================

Gateway
-------

* 'gateway', <gateway_name>, <device_type>, <device_name>, 'system', 'enable'

    * `source timestamp` - optional timestamp when component issued event
      register request

    * `payload` - JSON payload encoding boolean value which represents
      device's enabled status

* 'gateway', <gateway_name>, <device_type>, <device_name>, 'gateway', 'running'

    * `source timestamp` - required timestamp when Device is successfully
      created (started) or destroyed (stopped)

    * `payload` - JSON payload encoding boolean value set to `true` when
      Device is successfully created (started) or destroyed (stopped)
