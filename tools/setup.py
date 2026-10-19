#!/usr/bin/env python3
"""Initialize an independent signed feed using existing gh authentication.

No commit, push or workflow dispatch is performed. Checkpoints and the signing key
stay outside the checkout. A retry reconciles remote state before repeating a write.
"""
import argparse
import base64
import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from repository_config import (OFFICIAL_REPOSITORY, ToolError, check_fingerprint, check_repository,
                               dump_json, load_config, load_manifests, load_reserved, new_uuid,
                               parse_json_object, read_regular, run_main, same_repository, validate_config,
                               validate_manifest)

ENVIRONMENT = 'github-pages'
SECRET = 'INTERCEPTOR_REPOSITORY_KEY_B64'
WORKFLOW = 'publish.yml'
MASTER_POLICY = {'protected_branches': False, 'custom_branch_policies': True}


def parse_origin(value):
    """Accept only explicit github.com HTTPS/SSH origins, with no credentials."""
    match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([A-Za-z0-9._/-]+?)(?:\.git)?/?', value)
    if not match:
        raise ToolError('origin must be an explicit github.com HTTPS or SSH repository URL')
    return check_repository(match.group(1))


def _command(args, *, cwd=None, input_data=None, what='command', timeout=120, env=None):
    try:
        result = subprocess.run(args, cwd=cwd, input=input_data, capture_output=True,
                                timeout=timeout, env=env)
    except (OSError, subprocess.SubprocessError):
        raise ToolError(f'{what} failed; inspect authentication/tool installation and retry') from None
    if result.returncode:
        # Never echo commands, stdout or stderr: secret-bearing tools can include input.
        raise ToolError(f'{what} failed; inspect authentication/tool installation and retry')
    return result.stdout


def inspect_origin(root):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env['GIT_TERMINAL_PROMPT'] = '0'
    def git(*args):
        return _command(['git', '-C', str(root), *args], what='Git preflight', env=env).decode('utf-8').splitlines()
    top = git('rev-parse', '--show-toplevel')
    if len(top) != 1 or Path(top[0]).resolve() != root:
        raise ToolError('--root must be the Git checkout root')
    origins = git('remote', 'get-url', '--all', 'origin') + git('remote', 'get-url', '--push', '--all', 'origin')
    if not origins:
        raise ToolError('origin is missing')
    repositories = [parse_origin(url) for url in origins]
    if not all(same_repository(repo, repositories[0]) for repo in repositories):
        raise ToolError('origin fetch and push URLs must identify the same repository')
    return repositories[0]


def pages_url(repository):
    owner, name = check_repository(repository).split('/')
    prefix = '' if name.lower() == owner.lower() + '.github.io' else name + '/'
    return f'https://{owner.lower()}.github.io/{prefix}repository.json'


class GitHub:
    """Small gh adapter. Secret values travel only through stdin, never arguments."""
    def request(self, method, path, data=None, missing_ok=False):
        args = ['gh', 'api', '--hostname', 'github.com', '--include', '--method', method,
                '-H', 'Accept: application/vnd.github+json', '-H', 'X-GitHub-Api-Version: 2022-11-28', path]
        if data is not None:
            args += ['--input', '-']
        try:
            result = subprocess.run(args, input=dump_json(data) if data is not None else None,
                                    capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            raise ToolError('GitHub API request failed; inspect gh authentication and retry') from None
        raw = result.stdout.replace(b'\r\n', b'\n')
        header, separator, body = raw.partition(b'\n\n')
        status = re.match(rb'HTTP/\S+\s+(\d{3})\b', header)
        if status and int(status.group(1)) == 404 and missing_ok:
            return None
        if result.returncode or not status or not 200 <= int(status.group(1)) < 300:
            raise ToolError('GitHub API request failed; inspect gh permissions and retry')
        if not body.strip():
            return None
        try:
            return json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise ToolError('GitHub returned an invalid JSON response') from None

    def set_secret(self, repository, key_path):
        raw = private_file(key_path, length=32)
        _command(['gh', 'secret', 'set', SECRET, '--env', ENVIRONMENT, '--repo', 'github.com/' + repository],
                 input_data=base64.b64encode(raw), what='GitHub environment secret upload')


class NativeKeyTool:
    """Portable Bun Ed25519 primitives, keeping the app's raw 32-byte key format."""
    def __init__(self, root):
        self.root = root

    def create(self, path):
        output = _command([sys.executable, str(self.root / 'tools/repository_tool.py'), 'keygen', str(path)],
                          cwd=self.root, what='Signing key creation').decode('utf-8').strip()
        return check_fingerprint(output)

    def fingerprint(self, path):
        private_file(path, length=32)
        output = _command([sys.executable, str(self.root / 'tools/repository_tool.py'), 'fingerprint', str(path)],
                          cwd=self.root, what='Public fingerprint check').decode('utf-8').strip()
        return check_fingerprint(output)


def private_file(path, length=None):
    info = os.lstat(path)
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or info.st_mode & 0o777 != 0o600 or info.st_uid != os.getuid()):
        raise ToolError('setup state and signing key must be owned regular files with mode 0600')
    value = read_regular(path)
    if length is not None and len(value) != length:
        raise ToolError('signing key must contain exactly 32 bytes')
    return value


def private_directory(path, root):
    path = Path(os.path.abspath(path.expanduser()))
    if path == root or root in path.parents:
        raise ToolError('setup state and key must be outside the checkout')
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise ToolError('setup state directory must not contain symlinks')
        if ((ancestor / '.git').exists() or (ancestor / '.git').is_symlink()) or ancestor.name.lower() in ('public', 'www', 'htdocs', '_site'):
            raise ToolError('setup state and key must be outside Git and public directories')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o777 != 0o700 or info.st_uid != os.getuid():
        raise ToolError('setup state directory must be owned by you with mode 0700')
    return path


def save_state(path, state):
    fd, temporary = tempfile.mkstemp(prefix='.setup-state.', dir=path.parent)
    temp = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(dump_json(state))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp.exists():
            temp.unlink()


@contextlib.contextmanager
def state_lock(directory):
    path = directory / 'setup.lock'
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        private_file(path)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ToolError('another setup is using this checkpoint') from None
        yield
    finally:
        os.close(fd)


def collection(api, path, field):
    values = []
    for page in range(1, 1001):
        result = api.request('GET', f'{path}?per_page=100&page={page}')
        if not isinstance(result, dict) or not isinstance(result.get(field), list):
            raise ToolError('GitHub returned an unexpected paginated response')
        batch = result[field]
        if not all(isinstance(value, dict) for value in batch):
            raise ToolError('GitHub returned an invalid collection entry')
        values.extend(batch)
        if len(batch) < 100:
            return values
    raise ToolError('GitHub pagination exceeded the supported limit; inspect repository settings')


def environment_state(api, base, allow_empty=False):
    environment = api.request('GET', base + '/environments/' + ENVIRONMENT, missing_ok=True)
    if environment is None:
        return None
    if not isinstance(environment, dict):
        raise ToolError('GitHub returned an invalid environment response')
    if environment.get('deployment_branch_policy') != MASTER_POLICY:
        raise ToolError('existing github-pages environment is not restricted to custom master-only branches; inspect it manually')
    policies = collection(api, base + '/environments/' + ENVIRONMENT + '/deployment-branch-policies', 'branch_policies')
    if not policies and allow_empty:
        return environment
    if len(policies) != 1 or policies[0].get('name') != 'master' or policies[0].get('type') != 'branch':
        raise ToolError('existing deployment branch policies must contain exactly master (branch); protections were preserved')
    return environment


def pages_state(api, base, expected_url):
    pages = api.request('GET', base + '/pages', missing_ok=True)
    if pages is None:
        return None
    expected_base = expected_url[:-len('repository.json')]
    if (pages.get('cname') not in (None, '') or pages.get('build_type') != 'workflow'
            or pages.get('html_url') != expected_base):
        raise ToolError('existing Pages URL/domain/build configuration differs; inspect it manually')
    return pages


def secret_metadata(api, base):
    secrets = collection(api, base + '/environments/' + ENVIRONMENT + '/secrets', 'secrets')
    matches = [item for item in secrets if item.get('name') == SECRET]
    if len(matches) > 1:
        raise ToolError('GitHub returned duplicate signing secret metadata')
    if not matches:
        return None
    if not isinstance(matches[0].get('updated_at'), str) or not matches[0]['updated_at']:
        raise ToolError('GitHub signing secret metadata is incomplete')
    return {key: matches[0][key] for key in ('name', 'updated_at')}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def template_files(root, repository, url):
    config = load_config(root)
    reserved = load_reserved(root)
    if not same_repository(config['githubRepository'], OFFICIAL_REPOSITORY) or config['id'].upper() not in reserved['ids']:
        raise ToolError('checkout is already configured; its original setup checkpoint is required')
    manifests = load_manifests(root)
    files = {}
    originals = {}
    taken = {identifier.upper() for identifier in reserved['ids']}
    config = dict(config, githubRepository=repository, repositoryURL=url,
                  name=(repository.split('/')[1] + ' plugins')[:80], id=new_uuid(taken), publicKeyFingerprint=None)
    taken.add(config['id'])
    for name, manifest in manifests:
        manifest = dict(manifest, id=new_uuid(taken))
        taken.add(manifest['id'])
        files[f'manifests/{name}.json'] = manifest
    files['repository-config.json'] = validate_config(config)
    for name in files:
        originals[name] = digest(read_regular(root / name))
    return files, originals


def check_files(root, state, *, apply=False):
    # Paths come only from our checkpoint, but still validate before file access.
    if not isinstance(state.get('files'), dict) or set(state['files']) != set(state.get('originals', {})):
        raise ToolError('invalid setup checkpoint file manifest')
    if 'repository-config.json' not in state['files']:
        raise ToolError('invalid setup checkpoint configuration')
    for name, value in state['files'].items():
        if name != 'repository-config.json' and not re.fullmatch(r'manifests/[a-z0-9]+(?:-[a-z0-9]+)*\.json', name):
            raise ToolError('invalid setup checkpoint path')
        if name == 'repository-config.json':
            validate_config(value)
        else:
            validate_manifest(value, name)
        raw = read_regular(root / name)
        target = dump_json(value)
        if raw != target and (state.get('configured') or digest(raw) != state['originals'][name]):
            raise ToolError('configuration changed outside this setup; refusing to generate new identities or overwrite edits')
    if apply:
        for name, value in state['files'].items():
            path = root / name
            target = dump_json(value)
            if read_regular(path) == target:
                continue
            fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.setup.', dir=path.parent)
            temp = Path(temporary)
            os.fchmod(fd, 0o644)
            try:
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(target)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, path)
            finally:
                if temp.exists():
                    temp.unlink()


def setup_repository(root, api, keytool, *, state_dir=None):
    root = Path(root).resolve()
    repository = inspect_origin(root)
    if same_repository(repository, OFFICIAL_REPOSITORY):
        raise ToolError('setup refuses the official repository; create your own GitHub repository first')
    base = 'repos/' + repository
    remote = api.request('GET', base)
    if (not isinstance(remote, dict) or not same_repository(remote.get('full_name', ''), repository)
            or remote.get('private') is not False or remote.get('visibility') != 'public'
            or remote.get('default_branch') != 'master' or remote.get('permissions', {}).get('admin') is not True):
        raise ToolError('setup requires the matching public GitHub repository, admin access and default branch master')
    actions = api.request('GET', base + '/actions/permissions')
    if not isinstance(actions, dict) or actions.get('enabled') is not True:
        raise ToolError('GitHub Actions is disabled; existing restrictions were preserved')
    url = pages_url(repository)
    owner, name = repository.split('/')
    directory = private_directory(Path(state_dir) if state_dir is not None else
                                  Path.home() / '.config/interceptor/repositories' / (owner + '--' + name), root)
    checkpoint = directory / 'setup-state.json'
    key_path = directory / 'repository.key'
    with state_lock(directory):
        state = None
        if checkpoint.exists() or checkpoint.is_symlink():
            state = parse_json_object(private_file(checkpoint), 'setup checkpoint')
            if (state.get('schemaVersion') != 1 or state.get('repository') != repository
                    or state.get('root') != str(root) or state.get('url') != url):
                raise ToolError('setup checkpoint belongs to a different checkout or repository')
            check_files(root, state)
        environment = environment_state(api, base, allow_empty=bool(state and state.get('environment_pending')))
        pages = pages_state(api, base, url)
        secret = secret_metadata(api, base) if environment is not None else None
        if state is None:
            if secret is not None:
                raise ToolError('an unknown signing secret already exists; setup will not replace it')
            if key_path.exists() or key_path.is_symlink():
                raise ToolError('a signing key exists without its checkpoint; refusing rotation or replacement')
            files, originals = template_files(root, repository, url)
            state = {'schemaVersion': 1, 'repository': repository, 'root': str(root), 'url': url,
                     'files': files, 'originals': originals, 'fingerprint': None, 'configured': False,
                     'environment_pending': False, 'secret_pending': None, 'secret_metadata': None,
                     'complete': False}
            save_state(checkpoint, state)
        if key_path.exists() or key_path.is_symlink():
            private_file(key_path, length=32)
            fingerprint = keytool.fingerprint(key_path)
        else:
            if state['fingerprint'] is not None:
                raise ToolError('checkpoint signing key is missing; restore it rather than rotate it')
            fingerprint = keytool.create(key_path)
            private_file(key_path, length=32)
            if keytool.fingerprint(key_path) != fingerprint:
                raise ToolError('native key fingerprint did not match')
        check_fingerprint(fingerprint)
        if state['fingerprint'] not in (None, fingerprint):
            raise ToolError('checkpoint signing key fingerprint changed; refusing rotation')
        if fingerprint in load_reserved(root)['fingerprints']:
            raise ToolError('a reserved official signing key cannot initialize a template')
        state['fingerprint'] = fingerprint
        state['files']['repository-config.json']['publicKeyFingerprint'] = fingerprint
        save_state(checkpoint, state)
        check_files(root, state, apply=True)
        state['configured'] = True
        save_state(checkpoint, state)
        config_digest = digest(dump_json(state['files']))
        pending = {'fingerprint': fingerprint, 'configDigest': config_digest}
        if secret is not None:
            if state['secret_metadata'] is not None:
                if secret != state['secret_metadata']:
                    raise ToolError('signing secret metadata changed outside setup; refusing replacement')
            else:
                raise ToolError('a signing secret is visible without confirmed checkpoint metadata; manually reconcile the unconfirmed remote secret before retrying')
        elif state['secret_metadata'] is not None:
            raise ToolError('the configured signing secret disappeared; inspect repository settings')
        if environment is None:
            resuming_environment = state['environment_pending']
            state['environment_pending'] = True
            save_state(checkpoint, state)
            # Re-read before the create/update API: never PUT over an environment
            # that appeared since preflight, including its review protections.
            environment = environment_state(api, base, allow_empty=resuming_environment)
            if environment is None:
                api.request('PUT', base + '/environments/' + ENVIRONMENT, {'deployment_branch_policy': MASTER_POLICY})
            environment = environment_state(api, base, allow_empty=True)
            if environment is None:
                raise ToolError('environment creation was not confirmed; retry to reconcile')
        if state['environment_pending']:
            policies = collection(api, base + '/environments/' + ENVIRONMENT + '/deployment-branch-policies', 'branch_policies')
            if not policies:
                api.request('POST', base + '/environments/' + ENVIRONMENT + '/deployment-branch-policies',
                            {'name': 'master', 'type': 'branch'})
            environment_state(api, base)
            state['environment_pending'] = False
            save_state(checkpoint, state)
        if pages is None:
            api.request('POST', base + '/pages', {'build_type': 'workflow'})
            if pages_state(api, base, url) is None:
                raise ToolError('Pages creation was not confirmed; retry to reconcile')
        if state['secret_metadata'] is None:
            environment_state(api, base)
            current_secret = secret_metadata(api, base)
            if current_secret is not None:
                raise ToolError('a signing secret is visible without confirmed checkpoint metadata; manually reconcile the unconfirmed remote secret before retrying')
            # Intent preserves the selected key/configuration through a failure,
            # but cannot prove who wrote a visible remote secret. A retry uploads
            # only after reading the secret as absent; it never overwrites an
            # unconfirmed secret, even when this checkpoint recorded intent.
            state['secret_pending'] = pending
            save_state(checkpoint, state)
            api.set_secret(repository, key_path)
            observed = secret_metadata(api, base)
            if observed is None:
                raise ToolError('signing secret upload metadata is not visible yet; retry to reconcile')
            state['secret_metadata'] = observed
            state['secret_pending'] = None
            save_state(checkpoint, state)
        workflow = api.request('GET', base + '/actions/workflows/' + WORKFLOW)
        if not isinstance(workflow, dict) or workflow.get('state') not in ('active', 'disabled_fork', 'disabled_inactivity', 'disabled_manually'):
            raise ToolError('publishing workflow is unavailable; commit the template workflow before retrying')
        if workflow['state'] != 'active':
            api.request('PUT', base + '/actions/workflows/' + WORKFLOW + '/enable')
            if api.request('GET', base + '/actions/workflows/' + WORKFLOW).get('state') != 'active':
                raise ToolError('publishing workflow enablement was not confirmed; retry to reconcile')
        state['complete'] = True
        save_state(checkpoint, state)
        return {'url': url, 'fingerprint': fingerprint, 'published': False,
                'secretVerification': 'metadata only; GitHub never returns secret contents'}


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--state-dir', type=Path, help='private directory outside every Git checkout (default: ~/.config/interceptor/repositories/OWNER--NAME)')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    result = setup_repository(root, GitHub(), NativeKeyTool(root), state_dir=args.state_dir)
    print('Local and GitHub setup complete. No commit, push or deployment was started.')
    print('Registration URL (await publication and successful live verification): ' + result['url'])
    print('Public signing fingerprint: ' + result['fingerprint'])
    print('Publish the fingerprint through a trusted independent channel before users pin it.')
    print('Commit your configuration and push master; the publishing workflow verifies the live signed feed.')


if __name__ == '__main__':
    run_main(main)
