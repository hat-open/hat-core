import sys
import yaml
from pathlib import Path
sys.path += ['../../src_py']

import hat.asn1
from hat.drivers import snmp
from hat import util


def resolve_name(name_repo, name):
    if isinstance(name, str):
        return resolve_name(name_repo, name_repo[name]['oid'])
    if isinstance(name[0], str):
        return resolve_name(name_repo, name[0]) + name[1:]
    return name


async def async_main():

    path = Path('hat.asnrepo')
    if path.exists():
        asn1_repo = hat.asn1.load_repository(path)
    else:
        asn1_repo = hat.asn1.load_repository(Path('../../schemas_asn1'))
        hat.asn1.save_repository(asn1_repo, path)

    with open('names.yaml', encoding='utf-8') as f:
        name_repo = yaml.safe_load(f)

    master = await snmp.create_master(asn1_repo,
                                      snmp.Context('', 'KETSNMP'),
                                      remote_host='192.168.28.137',
                                      # remote_host='192.168.28.97',
                                      remote_port=161,
                                      version=snmp.Version.V2C)

    data = await master.get([
        resolve_name(name_repo, ['sysDescr', 0])
    ])
    print(data)

    await master.async_close()


def main():
    util.init_asyncio()
    util.run_asyncio(async_main())


if __name__ == '__main__':
    sys.exit(main())
