"""A repository can retain schema 1 JavaScript while adding routed TypeScript plugins."""
import copy
import json
import sys
from unittest.mock import patch

from helpers import Case, REPO
from test_http_hooks_v2 import V2
sys.path.insert(0, str(REPO / 'tools'))
import repository_config as config
import repository_tool as tool


class MixedRepositoryTests(Case):
    def test_samples_read_each_schema_from_its_own_source_directory(self):
        root = self.make_root()
        plugin = root / 'plugins/routed'
        hooks = plugin / 'hooks/api.example.com/search'
        hooks.mkdir(parents=True)
        manifest = copy.deepcopy(V2)
        (plugin / 'plugin.json').write_text(json.dumps({k: v for k, v in manifest.items() if k != 'matches'}))
        (hooks / 'POST.ts').write_text('Interceptor.attach({request:{onEnter(req){}}});')
        source = 'Interceptor.attach({request:{onEnter(req){}}});'
        key = 'hooks/api.example.com/search/POST.js'
        generated = root / 'build/scripts/routed' / key
        generated.parent.mkdir(parents=True)
        generated.write_text(source)
        site = root / 'build/site/plugins'; site.mkdir(parents=True)
        cases = []
        for name, hook in (('request-summary', 'request'), ('server-error-filter', 'response')):
            m = json.loads((root / f'manifests/{name}.json').read_text())
            code = (root / f'scripts/{name}.js').read_text()
            (site / f'{name}.json').write_bytes(config.package_bytes(m, code))
            cases.append({'name': name, 'plugin': name, 'hook': hook, 'event': {}, 'expected': {'actions': []}})
        (site / 'routed.json').write_bytes(config.package_bytes(manifest, {key: source}))
        cases.append({'name': 'routed', 'plugin': 'routed', 'phase': 'request.onEnter', 'event': {}, 'expected': {'actions': []}})
        (root / 'fixtures/cases.json').write_text(json.dumps(cases))
        (root / 'fixtures/config.json').write_text('{}')
        with patch.object(tool, 'simulator_binary', return_value='fixture-only'), \
             patch.object(tool, 'run_hook', return_value=(0, b'{"actions":[]}')) as runner:
            result = tool.samples(root, site.parent)
        self.assertIn('3 cases', result)
        self.assertEqual([call.kwargs.get('package') is not None for call in runner.call_args_list], [False, False, True])
