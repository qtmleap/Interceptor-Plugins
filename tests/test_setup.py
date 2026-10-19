"""Setup exercises fake GitHub state and disposable fixture keys only."""
import copy
import json
import sys
from pathlib import Path
from unittest import mock

from helpers import Case, OFFICIAL_REPOSITORY_ID, OFFICIAL_PLUGIN_IDS, tree_digest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import setup as setup_tool
from repository_config import ToolError

REPOSITORY = 'alice/my-plugins'
URL = 'https://alice.github.io/my-plugins/repository.json'
FINGERPRINT = 'c' * 64
SECRET = 'INTERCEPTOR_REPOSITORY_KEY_B64'


class FakeAPI:
    def __init__(self):
        self.repo = {'full_name': REPOSITORY, 'private': False, 'visibility': 'public',
                     'default_branch': 'master', 'permissions': {'admin': True}}
        self.environment = None
        self.policies = []
        self.secrets = []
        self.pages = None
        self.workflow = {'state': 'disabled_fork'}
        self.calls = []
        self.secret_writes = []
        self.fail_after = None

    def request(self, method, path, data=None, missing_ok=False):
        self.calls.append((method, path, copy.deepcopy(data)))
        base = 'repos/' + REPOSITORY
        if path == base:
            return copy.deepcopy(self.repo)
        if path == base + '/actions/permissions':
            return {'enabled': True, 'allowed_actions': 'all'}
        if path == base + '/environments/github-pages':
            if method == 'GET':
                return copy.deepcopy(self.environment)
            self.environment = {'id': 123, 'name': 'github-pages', 'protection_rules': [], **copy.deepcopy(data)}
            self._interrupt('environment')
            return copy.deepcopy(self.environment)
        if path.startswith(base + '/environments/github-pages/deployment-branch-policies?'):
            return {'branch_policies': copy.deepcopy(self.policies)}
        if path == base + '/environments/github-pages/deployment-branch-policies':
            self.policies.append({'id': 42, **data})
            self._interrupt('policy')
            return self.policies[-1]
        if path.startswith(base + '/environments/github-pages/secrets?'):
            return {'secrets': copy.deepcopy(self.secrets)}
        if path == base + '/pages':
            if method == 'GET':
                return copy.deepcopy(self.pages)
            self.pages = {'html_url': 'https://alice.github.io/my-plugins/', 'cname': None, 'build_type': 'workflow'}
            self._interrupt('pages')
            return copy.deepcopy(self.pages)
        if path == base + '/actions/workflows/deployment.yaml':
            return copy.deepcopy(self.workflow)
        if path == base + '/actions/workflows/deployment.yaml/enable':
            self.workflow['state'] = 'active'
            self._interrupt('workflow')
            return None
        raise AssertionError((method, path, data))

    def set_secret(self, repository, key_path):
        assert repository == REPOSITORY
        self.secret_writes.append(key_path.read_bytes())
        self.secrets = [{'name': SECRET, 'updated_at': '2026-10-18T00:00:00Z'}]
        self._interrupt('secret')

    def _interrupt(self, stage):
        if self.fail_after == stage:
            self.fail_after = None
            raise ToolError('simulated connection interruption')


class FakeKeyTool:
    def __init__(self):
        self.created = 0
        self.interrupt = False

    def create(self, path):
        self.created += 1
        with path.open('xb') as handle:
            handle.write(b'f' * 32)
        path.chmod(0o600)
        if self.interrupt:
            self.interrupt = False
            raise ToolError('simulated keygen interruption')
        return FINGERPRINT

    def fingerprint(self, path):
        assert path.read_bytes() == b'f' * 32
        return FINGERPRINT


class SetupTests(Case):
    def fixture(self):
        root = self.make_root()
        state = self.tmp / ('state-' + root.name)
        api, keys = FakeAPI(), FakeKeyTool()
        return root, state, api, keys

    def setup(self, root, state, api, keys):
        with mock.patch.object(setup_tool, 'inspect_origin', return_value=REPOSITORY):
            return setup_tool.setup_repository(root, api, keys, state_dir=state)

    def test_initialization_and_noop_resume_keep_identity_and_key(self):
        root, state, api, keys = self.fixture()
        result = self.setup(root, state, api, keys)
        config = self.config(root)
        self.assertEqual(config['githubRepository'], REPOSITORY)
        self.assertEqual(config['repositoryURL'], URL)
        self.assertEqual(config['publicKeyFingerprint'], FINGERPRINT)
        self.assertNotEqual(config['id'], OFFICIAL_REPOSITORY_ID)
        self.assertFalse(set(self.manifest_ids(root)) & set(OFFICIAL_PLUGIN_IDS))
        self.assertEqual(api.policies, [{'id': 42, 'name': 'master', 'type': 'branch'}])
        self.assertEqual(api.environment['deployment_branch_policy'], {'protected_branches': False, 'custom_branch_policies': True})
        self.assertEqual(result['url'], URL)
        self.assertFalse(result['published'])
        before = tree_digest(root)
        self.setup(root, state, api, keys)
        self.assertEqual(tree_digest(root), before)
        self.assertEqual(keys.created, 1)
        self.assertEqual(len(api.secret_writes), 1)
        for path in (state / 'setup-state.json', state / 'repository.key'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_each_uncertain_write_resumes_without_changing_ids_or_key(self):
        for stage in ('environment', 'policy', 'pages', 'workflow'):
            with self.subTest(stage=stage):
                root, state, api, keys = self.fixture()
                api.fail_after = stage
                with self.assertRaises(ToolError):
                    self.setup(root, state, api, keys)
                checkpoint = json.loads((state / 'setup-state.json').read_text())
                expected_id = checkpoint['files']['repository-config.json']['id']
                self.setup(root, state, api, keys)
                self.assertEqual(self.config(root)['id'], expected_id)
                self.assertEqual(keys.created, 1)
                self.assertEqual(len(api.policies), 1)
                self.assertTrue(api.secret_writes)
                self.assertEqual(len(set(api.secret_writes)), 1)

    def test_keygen_interruption_reuses_created_key(self):
        root, state, api, keys = self.fixture()
        keys.interrupt = True
        with self.assertRaises(ToolError):
            self.setup(root, state, api, keys)
        self.setup(root, state, api, keys)
        self.assertEqual(keys.created, 1)

    def test_remote_preflight_refuses_unsafe_states_before_modification(self):
        mutations = [
            lambda a: a.repo.update(private=True),
            lambda a: a.repo.update(permissions={'admin': False}),
            lambda a: a.repo.update(default_branch='main'),
            lambda a: a.repo.update(full_name='someone/else'),
            lambda a: (setattr(a, 'environment', {'deployment_branch_policy': setup_tool.MASTER_POLICY}), setattr(a, 'policies', [{'name': 'master', 'type': 'branch'}]), setattr(a, 'secrets', [{'name': SECRET, 'updated_at': 'unknown'}])),
            lambda a: setattr(a, 'pages', {'html_url': 'https://elsewhere.example/', 'cname': 'elsewhere.example', 'build_type': 'workflow'}),
            lambda a: setattr(a, 'environment', {'deployment_branch_policy': {'protected_branches': True, 'custom_branch_policies': False}}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                root, state, api, keys = self.fixture()
                mutate(api)
                before = tree_digest(root)
                with self.assertRaises(ToolError):
                    self.setup(root, state, api, keys)
                self.assertEqual(tree_digest(root), before)
                self.assertEqual(keys.created, 0)
                self.assertFalse(any(method != 'GET' for method, _, _ in api.calls))

    def test_existing_review_protections_are_preserved_without_put(self):
        root, state, api, keys = self.fixture()
        api.environment = {'id': 123, 'name': 'github-pages', 'protection_rules': [{'type': 'required_reviewers', 'reviewers': [{'id': 2}]}],
                           'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': True}}
        api.policies = [{'id': 42, 'name': 'master', 'type': 'branch'}]
        original = copy.deepcopy(api.environment)
        self.setup(root, state, api, keys)
        self.assertEqual(api.environment, original)
        self.assertFalse(any(method == 'PUT' and path.endswith('/environments/github-pages') for method, path, _ in api.calls))

    def test_ambiguous_branch_or_tag_policy_is_refused(self):
        for policies in ([{'name': '*', 'type': 'branch'}], [{'name': 'master', 'type': 'tag'}], [],
                         [{'name': 'master', 'type': 'branch'}, {'name': 'release/*', 'type': 'branch'}]):
            root, state, api, keys = self.fixture()
            api.environment = {'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': True}}
            api.policies = policies
            with self.assertRaises(ToolError):
                self.setup(root, state, api, keys)
            self.assertEqual(keys.created, 0)

    def test_checkpoint_rejects_edited_configuration_and_changed_secret(self):
        root, state, api, keys = self.fixture()
        self.setup(root, state, api, keys)
        self.write_config(root, name='changed after setup')
        with self.assertRaises(ToolError):
            self.setup(root, state, api, keys)
        root, state, api, keys = self.fixture()
        self.setup(root, state, api, keys)
        api.secrets[0]['updated_at'] = '2026-10-19T00:00:00Z'
        with self.assertRaises(ToolError):
            self.setup(root, state, api, keys)
        self.assertEqual(len(api.secret_writes), 1)

    def test_preconfigured_copy_without_checkpoint_is_refused(self):
        root, state, api, keys = self.fixture()
        self.write_config(root, githubRepository=REPOSITORY, id='B0A213C0-9D3C-47F5-ABB8-C15C7472E2AA', repositoryURL=URL)
        with self.assertRaises(ToolError):
            self.setup(root, state, api, keys)
        self.assertEqual(keys.created, 0)

    def test_user_pages_root_url_and_strict_origin_parsing(self):
        self.assertEqual(setup_tool.pages_url('alice/alice.github.io'), 'https://alice.github.io/repository.json')
        for value in ('https://github.com/alice/my-plugins.git', 'git@github.com:alice/my-plugins.git',
                      'ssh://git@github.com/alice/my-plugins'):
            self.assertEqual(setup_tool.parse_origin(value), REPOSITORY)
        for value in ('https://github.com.evil.example/alice/my-plugins', 'http://github.com/alice/my-plugins',
                      'https://token@github.com/alice/my-plugins', '/tmp/my-plugins', 'git@elsewhere:alice/my-plugins'):
            with self.assertRaises(ToolError):
                setup_tool.parse_origin(value)

    def test_paginated_rules_are_all_examined(self):
        root, state, api, keys = self.fixture()
        api.environment = {'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': True}}
        original = api.request
        def request(method, path, data=None, missing_ok=False):
            if 'deployment-branch-policies?' in path:
                page = int(path.rsplit('=', 1)[1])
                return {'branch_policies': ([{'name': 'master', 'type': 'branch'}] * 100 if page == 1 else [{'name': '*', 'type': 'branch'}])}
            return original(method, path, data, missing_ok)
        api.request = request
        with self.assertRaises(ToolError):
            self.setup(root, state, api, keys)
        self.assertEqual(keys.created, 0)

    def test_state_directory_symlink_and_key_mode_are_refused(self):
        root, state, api, keys = self.fixture()
        target = self.tmp / 'real-state'
        target.mkdir()
        state.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ToolError):
            self.setup(root, state, api, keys)
        root, state, api, keys = self.fixture()
        self.setup(root, state, api, keys)
        (state / 'repository.key').chmod(0o644)
        with self.assertRaises(ToolError):
            self.setup(root, state, api, keys)

    def test_secret_appearing_during_setup_is_not_overwritten(self):
        root, state, api, keys = self.fixture()
        original = api.request
        def request(method, path, data=None, missing_ok=False):
            result = original(method, path, data, missing_ok)
            if method == 'POST' and path.endswith('/pages'):
                api.secrets = [{'name': SECRET, 'updated_at': 'someone-else-created-this'}]
            return result
        api.request = request
        with self.assertRaises(ToolError):
            self.setup(root, state, api, keys)
        self.assertEqual(api.secret_writes, [])

    def test_partial_local_configuration_write_is_resumable(self):
        root, state, api, keys = self.fixture()
        original = setup_tool.os.replace
        calls = 0
        def replace(source, destination):
            nonlocal calls
            if Path(destination).parent == root / 'manifests':
                calls += 1
                if calls == 2:
                    raise OSError('simulated write interruption')
            return original(source, destination)
        with mock.patch.object(setup_tool.os, 'replace', side_effect=replace):
            with self.assertRaises(OSError):
                self.setup(root, state, api, keys)
        checkpoint = json.loads((state / 'setup-state.json').read_text())
        self.setup(root, state, api, keys)
        self.assertEqual(self.config(root)['id'], checkpoint['files']['repository-config.json']['id'])
        self.assertEqual(keys.created, 1)

    def test_official_repository_is_rejected_without_api_or_key_calls(self):
        root, state, api, keys = self.fixture()
        with mock.patch.object(setup_tool, 'inspect_origin', return_value='qtmleap/Interceptor-Plugins'):
            with self.assertRaises(ToolError):
                setup_tool.setup_repository(root, api, keys, state_dir=state)
        self.assertEqual(api.calls, [])
        self.assertEqual(keys.created, 0)

    def test_gh_secret_uses_stdin_and_error_output_is_redacted(self):
        root, state, api, keys = self.fixture()
        state.mkdir(mode=0o700)
        key = state / 'fixture.key'
        keys.create(key)
        with mock.patch.dict(setup_tool.os.environ, {'GH_HOST': 'elsewhere.example'}), mock.patch.object(setup_tool.subprocess, 'run') as run:
            run.return_value.returncode = 1
            run.return_value.stdout = b'private input echoed by a broken tool'
            with self.assertRaises(ToolError) as failure:
                setup_tool.GitHub().set_secret(REPOSITORY, key)
            self.assertNotIn('private input', str(failure.exception))
            args = run.call_args.args[0]
            self.assertNotIn('ZmZmZmZm', ' '.join(args))
            self.assertEqual(args[args.index('--repo') + 1], 'github.com/' + REPOSITORY)
            self.assertEqual(run.call_args.kwargs['input'], setup_tool.base64.b64encode(b'f' * 32))

    def test_gh_api_requires_observed_http_success_and_definite_404(self):
        with mock.patch.object(setup_tool.subprocess, 'run') as run:
            run.return_value.returncode = 1
            run.return_value.stdout = b'HTTP/2.0 404 Not Found\r\ncontent-type: application/json\r\n\r\n{"message":"Not Found"}'
            self.assertIsNone(setup_tool.GitHub().request('GET', 'repos/alice/missing', missing_ok=True))
            run.return_value.stdout = b''
            with self.assertRaises(ToolError):
                setup_tool.GitHub().request('GET', 'repos/alice/missing', missing_ok=True)
            run.return_value.returncode = 0
            run.return_value.stdout = b'HTTP/2.0 200 OK\r\ncontent-type: application/json\r\n\r\n{"enabled":true}'
            self.assertEqual(setup_tool.GitHub().request('GET', 'repos/alice/missing'), {'enabled': True})

    def test_uncertain_visible_secret_requires_manual_reconciliation(self):
        for changed_metadata in (False, True):
            with self.subTest(changed_metadata=changed_metadata):
                root, state, api, keys = self.fixture()
                api.fail_after = 'secret'
                with self.assertRaises(ToolError):
                    self.setup(root, state, api, keys)
                original_config = self.config(root)
                original_ids = self.manifest_ids(root)
                original_key = (state / 'repository.key').read_bytes()
                self.assertEqual(len(api.secret_writes), 1)
                if changed_metadata:
                    api.secrets[0]['updated_at'] = '2026-10-19T00:00:00Z'
                with self.assertRaisesRegex(ToolError, 'manually reconcile'):
                    self.setup(root, state, api, keys)
                self.assertEqual(len(api.secret_writes), 1, 'intent does not prove ownership of a visible secret')
                self.assertEqual(self.config(root), original_config)
                self.assertEqual(self.manifest_ids(root), original_ids)
                self.assertEqual((state / 'repository.key').read_bytes(), original_key)
                # Simulate a maintainer removing the unconfirmed secret after
                # inspecting settings. Setup itself never deletes remote secrets.
                api.secrets = []
                self.setup(root, state, api, keys)
                self.assertEqual(len(api.secret_writes), 2)
                self.assertEqual(len(set(api.secret_writes)), 1)
                self.assertEqual(self.config(root), original_config)
                self.assertEqual(self.manifest_ids(root), original_ids)
                self.assertEqual(keys.created, 1)

    def test_setup_cli_runs_on_linux(self):
        with mock.patch.object(setup_tool.sys, 'platform', 'linux'), \
             mock.patch.object(setup_tool, 'setup_repository') as initialize, \
             mock.patch.object(setup_tool, 'GitHub'), \
             mock.patch.object(setup_tool, 'NativeKeyTool'):
            initialize.return_value = {'url': 'https://alice.github.io/plugins/repository.json', 'fingerprint': 'a' * 64}
            setup_tool.main(['--root', str(self.tmp / 'absent')])
            initialize.assert_called_once()
