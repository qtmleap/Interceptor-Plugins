"""Guard the environment-creation boundary in the real publishing workflow."""
from helpers import REPO
import re
import unittest


class PublishGateTests(unittest.TestCase):
    def test_unconfigured_copies_fail_before_entering_signing_environment(self):
        workflow = (REPO / '.github/workflows/publish.yml').read_text()
        jobs = dict(re.findall(r'^  ([a-z][a-z-]*):\n(.*?)(?=^  [a-z][a-z-]*:|\Z)', workflow,
                               re.MULTILINE | re.DOTALL))
        self.assertIn('preflight', jobs)
        self.assertNotIn('environment:', jobs['preflight'])
        self.assertNotIn('secrets.', jobs['preflight'])
        self.assertIn('python3 tools/guard.py', jobs['preflight'])
        self.assertRegex(jobs['publish'], r'needs: \[preflight\]')
