"""Filesystem routes and authored metadata. This module never parses or executes TypeScript."""
import os
import re
import stat
from pathlib import Path

from repository_config import (ToolError, _host_ok, load_json, read_regular, require_exact_keys,
                               validate_manifest, DISPLAY_METADATA_KEYS, PUBLISHED_AT_KEY, SAMPLE_NAME_RE, MAX_SOURCE_BYTES)


def directory(path):
    if not stat.S_ISDIR(os.lstat(path).st_mode):
        raise ToolError(f'{path}: expected a real directory, no symlinks')


def metadata(path):
    value = load_json(path, str(path))
    required = ('schemaVersion', 'id', 'name', 'version', 'read', 'write', 'endpointBindings', 'settings')
    optional = tuple(key for key in DISPLAY_METADATA_KEYS + (PUBLISHED_AT_KEY,) if key in value)
    require_exact_keys(value, required + optional, str(path))
    if value['schemaVersion'] != 2:
        raise ToolError(f'{path}: authored route plugins require schemaVersion 2')
    # Reuse all identity, grant and settings validation without author-supplied routing.
    route = {'hosts': ['example.com'], 'methods': ['GET'], 'path': {'kind': 'exact', 'value': '/'},
             'hooks': {'request': {'onEnter': 'hooks/example.com/GET.js'}}}
    validate_manifest(dict(value, matches=[route]), str(path))
    return value


def discover(root):
    root = Path(root)
    base = root / 'plugins'
    if not os.path.lexists(base):
        return {}
    directory(base)
    plugins = {}
    for name in sorted(os.listdir(base)):
        if name == '.DS_Store':
            continue
        if not SAMPLE_NAME_RE.fullmatch(name) or len(name) > 64:
            raise ToolError(f'invalid plugin folder: {name}')
        plugin = base / name
        directory(plugin)
        meta = metadata(plugin / 'plugin.json')
        hooks = plugin / 'hooks'
        directory(hooks)
        routes, seen = [], set()
        for current, dirs, files in os.walk(hooks, followlinks=False):
            entries = [entry for entry in dirs + files if entry != '.DS_Store']
            if len({entry.casefold() for entry in entries}) != len(entries):
                raise ToolError(f'{current}: case-insensitive path collision')
            for entry in dirs:
                directory(Path(current) / entry)
            for entry in sorted(files):
                if entry == '.DS_Store':
                    continue
                file = Path(current) / entry
                relative = file.relative_to(hooks)
                parts = relative.parts
                if len(parts) < 2 or not _host_ok(parts[0]) or not re.fullmatch(r'[A-Z]{1,16}\.ts', parts[-1]):
                    raise ToolError(f'{file}: expected hooks/HOST/PATH/METHOD.ts')
                segments = parts[1:-1]
                if any(len(s) > 128 or not re.fullmatch(r'[A-Za-z0-9_~-][A-Za-z0-9._~-]*', s) or s in ('.', '..') for s in segments):
                    raise ToolError(f'{file}: unsupported route path')
                path = '/' + '/'.join(segments)
                method = parts[-1][:-3]
                key = 'hooks/' + relative.with_suffix('.js').as_posix()
                if len(key.encode('utf-8')) > 256:
                    raise ToolError(f'{file}: route file path exceeds 256 bytes')
                route = (parts[0], path, method)
                if route in seen:
                    raise ToolError(f'{file}: duplicate route')
                seen.add(route)
                text = read_regular(file, MAX_SOURCE_BYTES).decode('utf-8')
                if '\x00' in text:
                    raise ToolError(f'{file}: NUL in source')
                routes.append({'file': 'hooks/' + relative.as_posix(), 'emitted': key,
                               'host': parts[0], 'path': path, 'method': method})
        if not 1 <= len(routes) <= 16:
            raise ToolError(f'{plugin}: expected 1 to 16 route files')
        plugins[name] = {'metadata': meta, 'routes': sorted(routes, key=lambda r: (r['host'], r['path'], r['method']))}
    return plugins
