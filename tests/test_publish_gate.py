"""Guard the environment-creation boundary in the real publishing workflow."""
from helpers import REPO
import importlib
import re
import sys
import unittest

sys.path.insert(0, str(REPO / 'tools'))


class ReadOnlyAPI:
    def __init__(self, environment, policies=None, error=None):
        self.environment = environment
        self.policies = policies or []
        self.error = error
        self.calls = []

    def request(self, method, path, data=None, missing_ok=False):
        self.calls.append((method, path, data))
        if self.error:
            raise self.error
        if '/deployment-branch-policies?' in path:
            return {'branch_policies': self.policies}
        return self.environment


class PublishGateTests(unittest.TestCase):
    def test_unconfigured_copies_fail_before_entering_signing_environment(self):
        workflow = (REPO / '.github/workflows/deployment.yaml').read_text()
        jobs = dict(re.findall(r'^  ([a-z][a-z-]*):\n(.*?)(?=^  [a-z][a-z-]*:|\Z)', workflow,
                               re.MULTILINE | re.DOTALL))
        self.assertIn('preflight', jobs)
        self.assertNotIn('environment:', jobs['preflight'])
        self.assertNotIn('secrets.', jobs['preflight'])
        self.assertIn('python3 tools/guard.py', jobs['preflight'])
        self.assertIn('actions: read', jobs['preflight'])
        self.assertIn('GH_TOKEN: ${{ github.token }}', jobs['preflight'])
        self.assertIn('python3 tools/check_environment.py', jobs['preflight'])
        dependencies = re.search(r'^    needs: \[(.*?)\]', jobs['publish'], re.MULTILINE)
        self.assertIsNotNone(dependencies)
        self.assertEqual({part.strip() for part in dependencies.group(1).split(',')}, {'preflight', 'docs-build'})
        self.assertIn('needs: [preflight]', jobs['docs-build'])
        self.assertNotIn('environment:', jobs['docs-build'])
        self.assertNotIn('secrets.', jobs['docs-build'])
        self.assertNotIn('pages: write', jobs['docs-build'])
        self.assertNotIn('id-token: write', jobs['docs-build'])

    def test_remote_gate_accepts_only_existing_master_branch_policy(self):
        gate = importlib.import_module('check_environment')
        api = ReadOnlyAPI({'protection_rules': [{'type': 'required_reviewers'}],
            'deployment_branch_policy': {
            'protected_branches': False, 'custom_branch_policies': True}},
            [{'name': 'master', 'type': 'branch'}])
        gate.require_environment(api, 'sample-owner/my-plugins')
        self.assertEqual(len(api.calls), 2)
        self.assertTrue(all(method == 'GET' and data is None for method, _, data in api.calls))

    def test_missing_unreadable_or_unrestricted_environment_fails_closed(self):
        gate = importlib.import_module('check_environment')
        from repository_config import ToolError
        policy = {'deployment_branch_policy': {
            'protected_branches': False, 'custom_branch_policies': True}}
        cases = [ReadOnlyAPI(None), ReadOnlyAPI([]), ReadOnlyAPI({'deployment_branch_policy': None}),
                 ReadOnlyAPI({'deployment_branch_policy': {'protected_branches': True,
                                                         'custom_branch_policies': False}}),
                 ReadOnlyAPI(policy),
                 ReadOnlyAPI(policy, [{'name': '*', 'type': 'branch'}]),
                 ReadOnlyAPI(policy, [{'name': 'master', 'type': 'tag'}]),
                 ReadOnlyAPI(policy, [{'name': 'master', 'type': 'branch'},
                                      {'name': 'develop', 'type': 'branch'}]),
                 ReadOnlyAPI(None, error=ToolError('API unavailable'))]
        for api in cases:
            with self.subTest(environment=api.environment, policies=api.policies):
                with self.assertRaises(ToolError):
                    gate.require_environment(api, 'sample-owner/my-plugins')
                self.assertTrue(all(method == 'GET' and data is None for method, _, data in api.calls))

    def test_additional_policy_pages_are_not_ignored(self):
        gate = importlib.import_module('check_environment')
        from repository_config import ToolError

        class PagedAPI(ReadOnlyAPI):
            def request(self, method, path, data=None, missing_ok=False):
                result = super().request(method, path, data, missing_ok)
                if '/deployment-branch-policies?' in path:
                    if path.endswith('page=1'):
                        return {'branch_policies': [{'name': 'master', 'type': 'branch'}] * 100}
                    return {'branch_policies': [{'name': '*', 'type': 'branch'}]}
                return result

        api = PagedAPI({'deployment_branch_policy': {
            'protected_branches': False, 'custom_branch_policies': True}})
        with self.assertRaises(ToolError):
            gate.require_environment(api, 'sample-owner/my-plugins')
        self.assertTrue(any(path.endswith('page=2') for _, path, _ in api.calls))
        self.assertTrue(all(method == 'GET' and '/secrets' not in path and data is None
                            for method, path, data in api.calls))
