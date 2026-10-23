"""Bundled plugin icons: schema 2 `icon`, portable `assets`, and the real build. RED until implemented."""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import Case, REPO
import icon_fixtures as icons
import test_filesystem_hooks as filesystem_hooks
from test_http_hooks_v2 import v2

sys.path.insert(0, str(REPO / 'tools'))
import repository_config as config
import repository_tool as tool

HAS_BUN = shutil.which('bun') is not None and (REPO / 'node_modules').is_dir()
NEEDS_BUN = unittest.skipUnless(HAS_BUN, 'needs bun and installed node_modules (bun install --frozen-lockfile --ignore-scripts)')
SOURCE = {'hooks/api.example.com/search/POST.js': 'Interceptor.attach({request:{onEnter(req){}}});'}


def package(icon='icon.png', assets=None, **manifest):
    document = {'manifest': v2(**({'icon': icon} if icon else {}), **manifest), 'sourceFiles': copy.deepcopy(SOURCE)}
    if assets is not None:
        document['assets'] = assets
    return json.dumps(document).encode()


class IconManifestTests(unittest.TestCase):
    def test_authored_icon_metadata_is_accepted(self):
        for path in ('icon.png', 'Icon.png', 'icon.webp', 'assets/a-1_b.png', 'a' * 252 + '.png'):
            with self.subTest(path=path):
                config.validate_manifest(v2(icon=path), 'manifest')

    def test_invalid_icon_paths_are_rejected(self):
        for path in ('icon.gif', 'icon.PNG', '../icon.png', '/icon.png', 'a//b.png', 'ic on.png',
                     'é.png', 'a' * 253 + '.png', '', None, 7):
            with self.subTest(path=path), self.assertRaises(config.ToolError):
                config.validate_manifest(v2(icon=path), 'manifest')

    def test_schema1_icon_is_rejected(self):
        legacy = {'schemaVersion': 1, 'id': v2()['id'], 'name': 'Legacy', 'version': '1.0.0',
                  'subscriptions': [{'phase': 'request.completed', 'match': {'hosts': ['example.com']}}],
                  'read': {'metadata': ['host'], 'headers': [], 'queryKeys': [], 'body': {'mode': 'none'}},
                  'endpointBindings': ['preview'], 'settings': {}}
        config.validate_manifest(legacy, 'manifest')
        with self.assertRaises(config.ToolError):
            config.validate_manifest(dict(legacy, icon='icon.png'), 'manifest')


class IconPackageTests(unittest.TestCase):
    def test_shared_vectors_are_what_the_helpers_generate(self):
        self.assertEqual(json.loads(icons.VECTORS_PATH.read_text()), icons.vectors())

    def test_portable_package_with_valid_icon_is_accepted(self):
        for vector in icons.vectors():
            if not vector['expectedValid']:
                continue
            with self.subTest(vector=vector['name']):
                parsed = tool.validate_package(package(vector['path'], {vector['path']: vector['base64']}))
                self.assertEqual(parsed['assets'], {vector['path']: vector['base64']})

    def test_portable_package_with_invalid_icon_bytes_is_rejected(self):
        for vector in icons.vectors():
            if vector['expectedValid']:
                continue
            with self.subTest(vector=vector['name']), self.assertRaises(config.ToolError):
                tool.validate_package(package(vector['path'], {vector['path']: vector['base64']}))

    def test_raw_icon_size_is_limited_to_65536_bytes(self):
        for pad, ok in ((0, True), (65536 - len(icons.png()) - 12 - 2, True), (65536 - len(icons.png()) - 12 - 2 + 1, False)):
            data = icons.png(pad=pad)
            with self.subTest(size=len(data)):
                document = package('icon.png', {'icon.png': icons.b64(data)})
                if ok:
                    tool.validate_package(document)
                else:
                    with self.assertRaises(config.ToolError):
                        tool.validate_package(document)

    def test_assets_must_exactly_match_the_one_referenced_icon(self):
        good = icons.b64(icons.png())
        cases = {
            'missing assets': package('icon.png'),
            'empty assets': package('icon.png', {}),
            'orphan assets without icon': package(None, {'icon.png': good}),
            'mismatched key': package('icon.png', {'other.png': good}),
            'extra asset': package('icon.png', {'icon.png': good, 'extra.png': good}),
            'non-string asset': package('icon.png', {'icon.png': 7}),
            'non-canonical base64': package('icon.png', {'icon.png': good.rstrip('=')}),
            'whitespace in base64': package('icon.png', {'icon.png': good[:8] + '\n' + good[8:]}),
            'format mismatch': package('icon.webp', {'icon.webp': good}),
            'asset keyed like a source file': package('icon.png', {'icon.png': good, SOURCE_KEY: good}),
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(config.ToolError):
                tool.validate_package(data)

    def test_schema1_package_rejects_icon_and_assets(self):
        legacy = json.loads(json.dumps({'manifest': {
            'schemaVersion': 1, 'id': v2()['id'], 'name': 'Legacy', 'version': '1.0.0',
            'subscriptions': [{'phase': 'request.completed', 'match': {'hosts': ['example.com']}}],
            'read': {'metadata': ['host'], 'headers': [], 'queryKeys': [], 'body': {'mode': 'none'}},
            'endpointBindings': ['preview'], 'settings': {}}, 'source': ''}))
        tool.validate_package(json.dumps(legacy).encode())
        with_assets = dict(legacy, assets={'icon.png': icons.b64(icons.png())})
        with_icon = copy.deepcopy(legacy)
        with_icon['manifest']['icon'] = 'icon.png'
        for document in (with_assets, with_icon):
            with self.assertRaises(config.ToolError):
                tool.validate_package(json.dumps(document).encode())

    def test_package_without_icon_keeps_the_old_exact_bytes(self):
        manifest = v2()
        expected = json.dumps({'manifest': manifest, 'sourceFiles': SOURCE}, sort_keys=True,
                              separators=(',', ':'), ensure_ascii=False).encode()
        self.assertEqual(config.package_bytes(manifest, SOURCE), expected)
        self.assertNotIn(b'"assets"', expected)
        self.assertEqual(set(tool.validate_package(expected)), {'manifest', 'sourceFiles'})
        with self.assertRaises(config.ToolError):
            tool.validate_package(package(None, {}))


SOURCE_KEY = 'hooks/api.example.com/search/POST.js'


@NEEDS_BUN
class IconBuildTests(Case):
    def routed_root(self, icon_name='icon.webp', data=None):
        helper = filesystem_hooks.FilesystemHooksTests()
        helper.tmp = self.tmp
        root = helper.routed_root()
        shutil.copy(REPO / 'package.json', root / 'package.json')
        shutil.copy(REPO / 'tools/build_dev.py', root / 'tools')
        if icon_name:
            path = root / 'plugins/demo/plugin.json'
            metadata = json.loads(path.read_text())
            metadata['icon'] = icon_name
            path.write_text(json.dumps(metadata))
            (root / 'plugins/demo' / icon_name).write_bytes(data if data is not None else icons.webp(16, 16))
        return root

    def bun_build(self, root):
        return subprocess.run(['bun', 'run', 'build'], cwd=root, capture_output=True, text=True, timeout=60)

    def test_default_bun_build_emits_icon_assets_with_scripts_and_manifest(self):
        root = self.routed_root()
        self.ok(self.bun_build(root))
        built = json.loads((root / 'build/dev/plugins/demo.json').read_text())
        self.assertEqual(built['manifest']['icon'], 'icon.webp')
        self.assertEqual(built['assets'], {'icon.webp': icons.b64(icons.webp(16, 16))})
        self.assertEqual(json.loads((root / 'build/manifests/demo.json').read_text()), built['manifest'])
        for name, source in built['sourceFiles'].items():
            self.assertEqual((root / 'build/scripts/demo' / name).read_text(), source)

    def test_default_bun_build_without_icon_is_unchanged(self):
        root = self.routed_root(icon_name=None)
        self.ok(self.bun_build(root))
        built = json.loads((root / 'build/dev/plugins/demo.json').read_text())
        self.assertEqual(set(built), {'manifest', 'sourceFiles'})
        self.assertNotIn('icon', built['manifest'])

    def test_canonical_build_accepts_a_repository_under_tmp_alias(self):
        source = self.routed_root()
        with tempfile.TemporaryDirectory(prefix='plugin-icon-root-', dir='/tmp') as directory:
            root = Path(directory) / 'repository'
            shutil.copytree(source, root, symlinks=True)
            self.ok(self.run_tool(root, 'build', '--output', self.tmp / 'tmp-site'))
            built = json.loads((self.tmp / 'tmp-site/plugins/demo.json').read_text())
            self.assertEqual(built['assets'], {'icon.webp': icons.b64(icons.webp(16, 16))})

    def test_trusted_root_does_not_allow_symlinked_plugin_directory(self):
        root = self.routed_root()
        plugin = root / 'plugins/demo'
        moved = self.tmp / 'moved-plugin'
        plugin.rename(moved)
        plugin.symlink_to(moved, target_is_directory=True)
        metadata = json.loads((moved / 'plugin.json').read_text())
        with self.assertRaises(config.ToolError):
            config.load_icon_assets(root, [('demo', metadata, SOURCE)])

    def test_build_rejects_unusable_authored_icons_without_publishing(self):
        def missing(root):
            (root / 'plugins/demo/icon.webp').unlink()

        def symlink_leaf(root):
            (root / 'plugins/demo/icon.webp').unlink()
            real = self.tmp / 'real.webp'
            real.write_bytes(icons.webp())
            (root / 'plugins/demo/icon.webp').symlink_to(real)

        def symlink_parent(root):
            (root / 'plugins/demo/icon.webp').unlink()
            real = self.tmp / 'realdir'
            real.mkdir()
            (real / 'icon.webp').write_bytes(icons.webp())
            (root / 'plugins/demo/art').symlink_to(real, target_is_directory=True)
            path = root / 'plugins/demo/plugin.json'
            path.write_text(json.dumps(dict(json.loads(path.read_text()), icon='art/icon.webp')))

        def oversized(root):
            (root / 'plugins/demo/icon.webp').write_bytes(icons.webp() + b'\x00' * 65536)

        def wrong_format(root):
            (root / 'plugins/demo/icon.webp').write_bytes(icons.png())

        def too_wide(root):
            (root / 'plugins/demo/icon.webp').write_bytes(icons.webp(1025, 1))

        for mutate in (missing, symlink_leaf, symlink_parent, oversized, wrong_format, too_wide):
            with self.subTest(case=mutate.__name__):
                root = self.routed_root()
                mutate(root)
                result = self.bun_build(root)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertFalse((root / 'build/dev/plugins/demo.json').exists())


import struct
import zlib
import plugin_icons as grammar

_ihdr = lambda w=1, h=1, depth=8, color=6, comp=0, filt=0, inter=0: icons._chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, color, comp, filt, inter))
_idat = icons._chunk(b'IDAT', icons._stored(b'\x00' + bytes(4)))
_end = icons._chunk(b'IEND', b'')
_sig = b'\x89PNG\r\n\x1a\n'


def _riff(*chunks):
    body = b'WEBP' + b''.join(chunks)
    return b'RIFF' + struct.pack('<I', len(body)) + body


def _w(fourcc, body, pad=True):
    return fourcc + struct.pack('<I', len(body)) + body + (b'\0' if len(body) % 2 and pad else b'')


def _vp8x(flags, w=1, h=1):
    return _w(b'VP8X', bytes([flags, 0, 0, 0]) + (w - 1).to_bytes(3, 'little') + (h - 1).to_bytes(3, 'little'))


_VP8L = _w(b'VP8L', b'\x2f\0\0\0\0')
_VP8 = _w(b'VP8 ', b'\0\0\0\x9d\x01\x2a\x01\0\x01\0')


class IconGrammarTests(unittest.TestCase):
    def accepts(self, path, data):
        grammar.validate_icon_bytes(path, data)

    def rejects(self, path, data):
        with self.assertRaises(grammar.IconError):
            grammar.validate_icon_bytes(path, data)

    def test_png_structure(self):
        plte = lambda n: icons._chunk(b'PLTE', bytes(3 * n))
        good = {
            'minimal': _sig + _ihdr() + _idat + _end,
            'ancillary before idat': _sig + _ihdr() + icons._chunk(b'tEXt', b'a\0b') + _idat + _end,
            'split idat': _sig + _ihdr() + _idat + _idat + _end,
            'grayscale': _sig + _ihdr(color=0, depth=1) + _idat + _end,
            'indexed': _sig + _ihdr(color=3, depth=2) + plte(4) + _idat + _end,
            'rgb16': _sig + _ihdr(color=2, depth=16) + _idat + _end,
            'adam7': _sig + _ihdr(inter=1) + _idat + _end,
        }
        bad = {
            'no iend': _sig + _ihdr() + _idat,
            'trailing byte': _sig + _ihdr() + _idat + _end + b'\0',
            'trailing chunk': _sig + _ihdr() + _idat + _end + icons._chunk(b'tEXt', b'a\0b'),
            'iend with data': _sig + _ihdr() + _idat + icons._chunk(b'IEND', b'x'),
            'ihdr not first': _sig + icons._chunk(b'tEXt', b'a\0b') + _ihdr() + _idat + _end,
            'duplicate ihdr': _sig + _ihdr() + _ihdr() + _idat + _end,
            'short ihdr': _sig + icons._chunk(b'IHDR', bytes(12)) + _idat + _end,
            'zero width': _sig + _ihdr(w=0) + _idat + _end,
            'zero height': _sig + _ihdr(h=0) + _idat + _end,
            'height 1025': _sig + _ihdr(h=1025) + _idat + _end,
            'bad depth for color': _sig + _ihdr(color=2, depth=4) + _idat + _end,
            'unknown color type': _sig + _ihdr(color=1) + _idat + _end,
            'compression 1': _sig + _ihdr(comp=1) + _idat + _end,
            'filter 1': _sig + _ihdr(filt=1) + _idat + _end,
            'interlace 2': _sig + _ihdr(inter=2) + _idat + _end,
            'no idat': _sig + _ihdr() + _end,
            'empty idat': _sig + _ihdr() + icons._chunk(b'IDAT', b'') + _end,
            'non-contiguous idat': _sig + _ihdr() + _idat + icons._chunk(b'tEXt', b'a\0b') + _idat + _end,
            'indexed without plte': _sig + _ihdr(color=3, depth=8) + _idat + _end,
            'plte after idat': _sig + _ihdr(color=3, depth=8) + _idat + plte(1) + _end,
            'duplicate plte': _sig + _ihdr(color=3, depth=8) + plte(1) + plte(1) + _idat + _end,
            'plte length not multiple of 3': _sig + _ihdr(color=3, depth=8) + icons._chunk(b'PLTE', bytes(4)) + _idat + _end,
            'empty plte': _sig + _ihdr(color=3, depth=8) + plte(0) + _idat + _end,
            'plte 257 entries': _sig + _ihdr(color=3, depth=8) + plte(257) + _idat + _end,
            'plte larger than depth': _sig + _ihdr(color=3, depth=1) + plte(3) + _idat + _end,
            'plte in grayscale': _sig + _ihdr(color=0, depth=8) + plte(1) + _idat + _end,
            'plte in grayscale alpha': _sig + _ihdr(color=4, depth=8) + plte(1) + _idat + _end,
            'actl': _sig + _ihdr() + icons._chunk(b'acTL', bytes(8)) + _idat + _end,
            'fctl': _sig + _ihdr() + _idat + icons._chunk(b'fcTL', bytes(26)) + _end,
            'fdat': _sig + _ihdr() + _idat + icons._chunk(b'fdAT', bytes(4)) + _end,
            'unknown critical chunk': _sig + _ihdr() + icons._chunk(b'ZZZZ', b'') + _idat + _end,
            'reserved third letter lowercase': _sig + _ihdr() + icons._chunk(b'tExt', b'') + _idat + _end,
            'non-letter chunk type': _sig + _ihdr() + icons._chunk(b'tE1t', b'') + _idat + _end,
            'bad crc on ancillary': _sig + _ihdr() + icons._chunk(b'tEXt', b'a')[:-1] + bytes([icons._chunk(b'tEXt', b'a')[-1] ^ 1]) + _idat + _end,
            'bad signature': b'\x89PNG\r\n\x1a\x0b' + _ihdr() + _idat + _end,
            'truncated': (_sig + _ihdr() + _idat + _end)[:-1],
            'empty': b'',
        }
        for name, data in good.items():
            with self.subTest(good=name):
                self.accepts('icon.png', data)
        for name, data in bad.items():
            with self.subTest(bad=name):
                self.rejects('icon.png', data)

    def test_png_ancillary_payload_is_opaque(self):
        self.accepts('icon.png', _sig + _ihdr() + icons._chunk(b'tEXt', bytes(range(256))) + _idat + _end)

    def test_webp_structure(self):
        good = {
            'vp8l': _riff(_VP8L),
            'vp8': _riff(_VP8),
            'vp8x with vp8l': _riff(_vp8x(0), _VP8L),
            'vp8x alpha flag without alph on vp8l': _riff(_vp8x(0x10), _VP8L),
            'vp8x icc': _riff(_vp8x(0x20), _w(b'ICCP', b'abc'), _VP8L),
            'vp8x alph vp8': _riff(_vp8x(0x10), _w(b'ALPH', b'\0'), _VP8),
            'vp8x exif xmp after image': _riff(_vp8x(0x0C), _VP8L, _w(b'EXIF', b'e'), _w(b'XMP ', b'x')),
            'unknown printable chunk ignored': _riff(_VP8L, _w(b'abcd', b'zz')),
            'odd chunk padded': _riff(_w(b'abcd', b'z'), _VP8L),
        }
        bad = {
            'riff size too small': _riff(_VP8L)[:4] + struct.pack('<I', 4) + _riff(_VP8L)[8:],
            'riff size too large': _riff(_VP8L)[:4] + struct.pack('<I', 9999) + _riff(_VP8L)[8:],
            'trailing byte': _riff(_VP8L) + b'\0',
            'wrong form': b'RIFF' + _riff(_VP8L)[4:8] + b'WEBX' + _riff(_VP8L)[12:],
            'no image': _riff(_w(b'abcd', b'zz')),
            'two images': _riff(_VP8L, _VP8),
            'nonzero odd padding': _riff(_w(b'abcd', b'z')[:-1] + b'\x01', _VP8L),
            'non-printable fourcc': _riff(_w(b'ab\x01d', b''), _VP8L),
            'chunk past end': _riff(b'abcd' + struct.pack('<I', 50) + b'zz', ),
            'vp8x not first': _riff(_w(b'abcd', b''), _vp8x(0), _VP8L),
            'vp8x wrong size': _riff(_w(b'VP8X', bytes(11)), _VP8L),
            'vp8x animation flag': _riff(_vp8x(0x02), _VP8L),
            'vp8x reserved flag low': _riff(_vp8x(0x01), _VP8L),
            'vp8x reserved flag high': _riff(_vp8x(0x40), _VP8L),
            'vp8x reserved bytes': _riff(_w(b'VP8X', bytes([0, 1, 0, 0, 0, 0, 0, 0, 0, 0])), _VP8L),
            'vp8x canvas mismatch': _riff(_vp8x(0, 2, 1), _VP8L),
            'anim': _riff(_vp8x(0), _w(b'ANIM', bytes(6)), _VP8L),
            'anmf': _riff(_vp8x(0), _w(b'ANMF', bytes(16)), _VP8L),
            'icc without vp8x': _riff(_w(b'ICCP', b'abc'), _VP8L),
            'icc without flag': _riff(_vp8x(0), _w(b'ICCP', b'abc'), _VP8L),
            'flag without icc': _riff(_vp8x(0x20), _VP8L),
            'icc after image': _riff(_vp8x(0x20), _VP8L, _w(b'ICCP', b'abc')),
            'duplicate icc': _riff(_vp8x(0x20), _w(b'ICCP', b'a'), _w(b'ICCP', b'a'), _VP8L),
            'exif before image': _riff(_vp8x(0x08), _w(b'EXIF', b'e'), _VP8L),
            'xmp before image': _riff(_vp8x(0x04), _w(b'XMP ', b'x'), _VP8L),
            'exif without flag': _riff(_vp8x(0), _VP8L, _w(b'EXIF', b'e')),
            'flag without xmp': _riff(_vp8x(0x04), _VP8L),
            'alph without vp8x': _riff(_w(b'ALPH', b'\0'), _VP8),
            'alph without alpha flag': _riff(_vp8x(0), _w(b'ALPH', b'\0'), _VP8),
            'empty alph': _riff(_vp8x(0x10), _w(b'ALPH', b''), _VP8),
            'alph after vp8': _riff(_vp8x(0x10), _VP8, _w(b'ALPH', b'\0')),
            'alph is invalid for vp8l': _riff(_vp8x(0x10), _w(b'ALPH', b'\0'), _VP8L),
            'duplicate alph': _riff(_vp8x(0x10), _w(b'ALPH', b'\0'), _w(b'ALPH', b'\0'), _VP8),
            'vp8 too short': _riff(_w(b'VP8 ', bytes(9))),
            'vp8 interframe': _riff(_w(b'VP8 ', b'\x01\0\0\x9d\x01\x2a\x01\0\x01\0')),
            'vp8 bad start code': _riff(_w(b'VP8 ', b'\0\0\0\x9d\x01\x2b\x01\0\x01\0')),
            'vp8 horizontal scale': _riff(_w(b'VP8 ', b'\0\0\0\x9d\x01\x2a\x01\x40\x01\0')),
            'vp8 vertical scale': _riff(_w(b'VP8 ', b'\0\0\0\x9d\x01\x2a\x01\0\x01\x80')),
            'vp8 zero width': _riff(_w(b'VP8 ', b'\0\0\0\x9d\x01\x2a\0\0\x01\0')),
            'vp8 width 1025': _riff(_w(b'VP8 ', b'\0\0\0\x9d\x01\x2a\x01\x04\x01\0')),
            'vp8l too short': _riff(_w(b'VP8L', b'\x2f\0\0\0')),
            'vp8l bad magic': _riff(_w(b'VP8L', b'\x2e\0\0\0\0')),
            'vp8l version bits': _riff(_w(b'VP8L', b'\x2f\0\0\0\x20')),
            'vp8l width 1025': _riff(_w(b'VP8L', b'\x2f\0\x04\0\0')),
            'truncated header': b'RIFF\x04\0\0\0WEBP',
            'empty': b'',
        }
        for name, data in good.items():
            with self.subTest(good=name):
                self.accepts('icon.webp', data)
        for name, data in bad.items():
            with self.subTest(bad=name):
                self.rejects('icon.webp', data)

    def test_vp8_dimensions_use_fourteen_bits(self):
        self.assertEqual(grammar.validate_webp(_riff(_w(b'VP8 ', b'\0\0\0\x9d\x01\x2a\x00\x04\x00\x04'))), (1024, 1024))

    def test_format_must_match_the_path_suffix_and_size_limits_apply(self):
        self.rejects('icon.png', icons.webp())
        self.rejects('icon.webp', icons.png())
        self.rejects('icon.png', b'')
        self.accepts('Icon.png', icons.png())
        self.rejects('Icon.PNG', icons.png())

    def test_asset_base64_must_be_canonical(self):
        good = icons.b64(icons.png())
        for bad in (good + '=', good[:8] + '_' + good[9:], ' ' + good, good + '\n', 7, None):
            with self.subTest(value=bad), self.assertRaises(grammar.IconError):
                grammar.decode_asset('icon.png', bad)
        self.assertEqual(grammar.decode_asset('icon.png', good), icons.png())


class IconSafeReadTests(Case):
    def read(self, plugin, icon):
        return grammar.read_icon_file(plugin, icon)

    def test_reads_regular_nested_file_and_rejects_unsafe_ones(self):
        plugin = self.tmp / 'plugin'
        (plugin / 'assets').mkdir(parents=True)
        (plugin / 'assets/Icon.png').write_bytes(icons.png())
        self.assertEqual(self.read(plugin, 'assets/Icon.png'), icons.png())
        outside = self.tmp / 'outside'
        outside.mkdir()
        (outside / 'icon.png').write_bytes(icons.png())
        (plugin / 'link').symlink_to(outside, target_is_directory=True)
        (plugin / 'leaf.png').symlink_to(outside / 'icon.png')
        (plugin / 'dir.png').mkdir()
        (plugin / 'big.png').write_bytes(b'\0' * 65537)
        for icon in ('link/icon.png', 'leaf.png', 'dir.png', 'big.png', 'missing.png', '../outside/icon.png',
                     '/etc/x.png', 'a\\b.png', 'assets//Icon.png', 'assets/./Icon.png'):
            with self.subTest(icon=icon), self.assertRaises(grammar.IconError):
                self.read(plugin, icon)

    def test_symlinked_plugin_directory_is_refused(self):
        real = self.tmp / 'real'
        real.mkdir()
        (real / 'icon.png').write_bytes(icons.png())
        (self.tmp / 'plugin').symlink_to(real, target_is_directory=True)
        with self.assertRaises(grammar.IconError):
            self.read(self.tmp / 'plugin', 'icon.png')

    def test_symlinked_parent_of_plugin_directory_is_refused(self):
        real = self.tmp / 'real'
        (real / 'plugin').mkdir(parents=True)
        (real / 'plugin/icon.png').write_bytes(icons.png())
        alias = self.tmp / 'alias'
        alias.symlink_to(real, target_is_directory=True)
        with self.assertRaises(grammar.IconError):
            self.read(alias / 'plugin', 'icon.png')


class IconRepositoryToolTests(Case):
    """publish / verify-local / samples-adjacent behaviour for packages with and without icons."""

    def test_runtime_case_forwards_the_complete_validated_icon_package(self):
        _, data = self.site()
        parsed = tool.validate_package(data)
        phase, forwarded = tool._case_route({'phase': 'request.onEnter'}, parsed, 0)
        self.assertEqual(phase, 'request.onEnter')
        self.assertEqual(forwarded, data)

    def site(self, assets_icon=True, tamper=None):
        site = self.tmp / 'site'
        (site / 'plugins').mkdir(parents=True)
        manifest = v2(**({'icon': 'icon.png'} if assets_icon else {}))
        data = config.package_bytes(manifest, SOURCE, {'icon.png': icons.b64(icons.png())} if assets_icon else None)
        if tamper:
            data = tamper(data)
        (site / 'plugins/demo.json').write_bytes(data)
        return site, data

    def test_package_bytes_with_icon_are_deterministic_and_validate(self):
        site, data = self.site()
        manifest = v2(icon='icon.png')
        again = config.package_bytes(manifest, SOURCE, {'icon.png': icons.b64(icons.png())})
        self.assertEqual(data, again)
        self.assertEqual(json.loads(data)['assets'], {'icon.png': icons.b64(icons.png())})
        tool.validate_package(data)

    def test_package_bytes_reject_inconsistent_assets(self):
        good = icons.b64(icons.png())
        for manifest, assets in ((v2(), {'icon.png': good}), (v2(icon='icon.png'), None), (v2(icon='icon.png'), {}),
                                 (v2(icon='icon.png'), {'other.png': good}), (v2(icon='icon.png'), {'icon.png': 'AAAA'})):
            with self.subTest(manifest=manifest.get('icon'), assets=assets), self.assertRaises(config.ToolError):
                config.package_bytes(manifest, SOURCE, assets)

    def test_publish_and_verify_local_accept_an_iconed_package_and_pin_its_bytes(self):
        site, data = self.site()
        tool.publish(site, v2()['id'], 'Feed', 1, None, now=1_800_000_000)
        envelope = json.loads((site / 'repository.json').read_text())
        self.assertIn('payload', envelope)
        index = json.loads(__import__('base64').b64decode(envelope['payload']))
        entry = index['plugins'][0]
        self.assertEqual(entry['size'], len(data))
        self.assertEqual(entry['sha256'], __import__('hashlib').sha256(data).hexdigest())
        self.assertNotIn('icon', entry)
        self.assertNotIn('assets', entry)

    def test_publish_rejects_a_tampered_icon_package(self):
        def corrupt(data):
            document = json.loads(data)
            raw = icons.png(bad_crc=True)
            document['assets']['icon.png'] = icons.b64(raw)
            return json.dumps(document).encode()
        site, _ = self.site(tamper=corrupt)
        with self.assertRaises(config.ToolError):
            tool.publish(site, v2()['id'], 'Feed', 1, None, now=1_800_000_000)
        self.assertFalse((site / 'repository.json').exists())

    def test_legacy_schema2_bytes_have_no_assets(self):
        site, data = self.site(assets_icon=False)
        self.assertNotIn(b'assets', data)
        self.assertNotIn(b'"icon"', data)
