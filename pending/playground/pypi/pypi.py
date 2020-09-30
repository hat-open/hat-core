import aiohttp
import hashlib
import packaging.requirements
import packaging.tags
import packaging.utils
import packaging.version
import pathlib
import sys

from hat import util


Environment = util.namedtuple('Environment',
                              ['pypi_url', 'str'],
                              ['python_version', 'str'],
                              ['interpreters', 'List[str]'],
                              ['platforms', 'List[str]'])


async def download(requirements, out_dir, env=None):
    """Download PyPI packages

    Args:
        requirements (Iterable[str]): required packages
        out_dir (os.PathLike): output directory
        env (Optional[Environment]): python environment

    """
    out_dir = pathlib.Path(out_dir)
    env = env or _get_default_env()
    requirements = _parse_requirements(env, requirements)

    async with aiohttp.ClientSession() as session:

        cache = _Cache(env, session)
        dependencies = await _get_dependencies(cache, requirements)

        for name, version in dependencies.items():
            links = await cache.get_links(name, version)
            links = {(i.tag and i.tag.platform): i for i in links}

            async def write(platform):
                return await _write_link(session, out_dir, name,
                                         links[platform])

            if 'any' in links:
                await write('any')
                continue

            download_sdist = False
            for platform in env.platforms:
                if platform in links:
                    await write(platform)
                else:
                    download_sdist = True

            if download_sdist and None in links:
                await write(None)


_Link = util.namedtuple('_Link',
                        ['filename', 'str'],
                        ['md5', 'str'],
                        ['url', 'str'],
                        ['tag', 'Optional[packaging.tags.Tag]'])


class _Cache:

    def __init__(self, env, session):
        self._env = env
        self._session = session
        self._versions = {}
        self._requirements = {}
        self._links = {}

    async def get_versions(self, name):
        if name not in self._versions:
            await self._update(name)
        return self._versions[name]

    async def get_requirements(self, name, version):
        key = (name, version)
        if key not in self._requirements:
            await self._update(name, version)
        return self._requirements[key]

    async def get_links(self, name, version):
        key = name, version
        if key not in self._links:
            await self._update(name, version)
        return self._links[key]

    async def _update(self, name, version=None):
        pypi_json = await self._read_pypi_json(name, version)
        name = packaging.utils.canonicalize_name(pypi_json['info']['name'])
        version = packaging.version.parse(pypi_json['info']['version'])
        key = name, version
        self._cache_versions(name, pypi_json)
        self._cache_requirements(key, pypi_json)
        self._cache_links(key, pypi_json)

    async def _read_pypi_json(self, name, version):
        if version:
            url = f"{self._env.pypi_url}/{name}/{version}/json"
        else:
            url = f"{self._env.pypi_url}/{name}/json"
        async with self._session.get(url) as resp:
            return await resp.json()

    def _cache_versions(self, name, pypi_json):
        self._versions[name] = sorted(
            (packaging.version.parse(version)
             for version in pypi_json['releases'].keys()),
            reverse=True)

    def _cache_requirements(self, key, pypi_json):
        requirements = pypi_json['info'].get('requires_dist') or []
        self._requirements[key] = list(
            _parse_requirements(self._env, requirements))

    def _cache_links(self, key, pypi_json):
        self._links[key] = list(_parse_links(self._env, pypi_json['urls']))


async def _get_dependencies(cache, requirements):

    async def walk(specifiers, requirements):
        if not requirements:
            yield {}
            return
        requirement, requirements = requirements[0], requirements[1:]
        name = packaging.utils.canonicalize_name(requirement.name)
        versions = await cache.get_versions(name)
        specifier = specifiers.get(name)
        if requirement.specifier:
            if specifier:
                specifier = specifier & requirement.specifier
            else:
                specifier = requirement.specifier
            specifiers = dict(specifiers, **{name: specifier})
        if specifier:
            versions = specifier.filter(versions)
        for version in versions:
            additional = await cache.get_requirements(name, version)
            async for dependencies in walk(specifiers,
                                           requirements + additional):
                if name not in dependencies:
                    yield dict(dependencies, **{name: version})
                elif dependencies[name] == version:
                    yield dependencies

    async for dependencies in walk({}, list(requirements)):
        return dependencies


async def _write_link(session, out_dir, name, link):
    path = out_dir / name / link.filename
    if path.exists():
        with open(path, 'rb') as f:
            md5 = hashlib.md5(f.read()).hexdigest()
            if md5.lower() == link.md5.lower():
                return
    async with session.get(link.url) as resp:
        data = await resp.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)


def _get_default_env():
    major = sys.version_info[0]
    minor = sys.version_info[1]
    return Environment(pypi_url='https://pypi.org/pypi',
                       python_version=f'{major}.{minor}',
                       interpreters=[f'py{major}',
                                     f'cp{major}',
                                     f'cp{major}{minor}'],
                       platforms=['win32',
                                  'manylinux1_x86_64'])


def _parse_requirements(env, requirements):
    env = {'python_version': env.python_version,
           'extra': ''}
    for requirement in requirements:
        requirement = requirement.strip()
        if not requirement or requirement.startswith('#'):
            continue
        requirement = packaging.requirements.Requirement(requirement)
        if not requirement.marker or requirement.marker.evaluate(env):
            yield requirement


def _parse_links(env, urls):
    for url in urls:
        link = _Link(filename=url['filename'],
                     md5=url['md5_digest'],
                     url=url['url'],
                     tag=None)
        if url['packagetype'] == 'sdist':
            yield link
            continue
        if url['packagetype'] != 'bdist_wheel':
            continue
        stem = url['filename'].rsplit('.', 1)[0]
        tag_str = '-'.join(stem.rsplit('-', 3)[1:])
        tags = packaging.tags.parse_tag(tag_str)
        for tag in tags:
            if tag.interpreter not in env.interpreters:
                continue
            if tag.platform != 'any' and tag.platform not in env.platforms:
                continue
            yield link._replace(tag=tag)
