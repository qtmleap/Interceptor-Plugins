"""Keep the authoring container independent from private host state and macOS signing."""
import json
import unittest

from helpers import REPO


class DevcontainerTests(unittest.TestCase):
    def test_unprivileged_workspace_without_host_credentials_or_docker(self):
        config = json.loads((REPO / '.devcontainer/devcontainer.json').read_text())
        self.assertEqual(config['remoteUser'], 'vscode')
        self.assertEqual(config['service'], 'app')
        self.assertFalse(config.get('mounts'))
        self.assertFalse(config.get('forwardPorts'))
        self.assertFalse(config.get('remoteEnv'))
        features = config['features']
        self.assertIn('ghcr.io/tkgstrator/commitguard:1', features)
        self.assertIsNot(features['ghcr.io/tkgstrator/commitguard:1'].get('autoActivate'), False)
        self.assertFalse(any('docker' in name for name in features))

    def test_lifecycle_installs_frozen_dependencies_without_publishing(self):
        config = json.loads((REPO / '.devcontainer/devcontainer.json').read_text())
        self.assertEqual(config['postCreateCommand'], ['bash', '.devcontainer/postCreateCommand.sh'])
        script = (REPO / '.devcontainer/postCreateCommand.sh').read_text()
        self.assertIn('bun install --frozen-lockfile --ignore-scripts', script)
        self.assertNotIn('tools/setup.py', script)
        self.assertNotIn('tools/publish.sh', script)
        self.assertNotIn('auth login', script)

    def test_container_uses_the_same_pinned_bun(self):
        version = (REPO / '.bun-version').read_text().strip()
        dockerfile = (REPO / '.devcontainer/Dockerfile').read_text()
        self.assertIn(f'FROM oven/bun:{version}@sha256:', dockerfile)
        self.assertIn('python3', dockerfile)
        self.assertIn('openssl', dockerfile)
        self.assertIn('COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun', dockerfile)
