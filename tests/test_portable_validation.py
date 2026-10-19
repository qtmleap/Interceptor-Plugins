"""Portable validators must reject documents that the app's Swift parser rejects."""
import copy
import json
from pathlib import Path
import sys
import unittest

from helpers import REPO
sys.path.insert(0, str(REPO / 'tools'))
import repository_config as config
import repository_tool as tool


class PortableValidationTests(unittest.TestCase):
    def test_identifiers_and_timestamps_must_match_the_entire_ascii_value(self):
        with self.assertRaises(config.ToolError):
            config.check_uuid('11111111-2222-4333-8444-555555555555\n', 'id')
        self.assertIsNone(tool.parse_time('2026-01-01T00:00:00Z\n'))
        manifest = json.loads((REPO / 'manifests/request-summary.json').read_text())
        for version in ('١.٢.٣', '1.2.3\n'):
            with self.subTest(version=version), self.assertRaises(config.ToolError):
                config.validate_manifest(dict(manifest, version=version), 'manifest')

    def test_configuration_files_use_strict_json(self):
        for text in ('{"é":1,"e\\u0301":2}', '{"x":"\\ud800"}', '{"x":9007199254740992}', '{"x":1e999}'):
            with self.subTest(text=text), self.assertRaises(config.ToolError):
                config.parse_json_object(text.encode(), 'config')

    def test_utf8_settings_use_the_encoded_size(self):
        manifest = json.loads((REPO / 'manifests/request-summary.json').read_text())
        manifest['settings'] = {'text': 'あ' * 1400}
        config.validate_manifest(manifest, 'manifest')
