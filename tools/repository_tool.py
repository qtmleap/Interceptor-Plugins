#!/usr/bin/env python3
"""Portable Linux/macOS twin of interceptor-repository and interceptor-samples-check.

  repository_tool.py keygen KEY
  repository_tool.py fingerprint KEY
  repository_tool.py publish DIR --id UUID --name NAME --sequence N [--key KEY]
  repository_tool.py samples ROOT DIR
  repository_tool.py legacy-samples ROOT
  repository_tool.py verify-local ROOT DIR [--signed]
  repository_tool.py previous ROOT FILE
  repository_tool.py verify-live ROOT SEQUENCE

The app's envelope, schema limits, signature domain and raw 32-byte Ed25519 seed are preserved exactly.
Ed25519 goes through tools/signing.mjs (Bun, else Node); secrets only travel over stdin.
"""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import uuid
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_previous  # noqa: E402
from repository_config import (ToolError, UsageError, UUID_RE, _SEMVER, _list_dir, canonical_url,  # noqa: E402
                               check_uuid, is_display_name, is_int, load_config, load_json, parse_args,
                               read_regular, require_exact_keys, run_main, validate_manifest,
                               DISPLAY_METADATA_KEYS, validate_display_metadata, parse_time, _epoch, _TIME_RE)  # noqa: F401

HERE = Path(__file__).resolve().parent
SIGNING = HERE / "signing.mjs"
SIGNATURE_DOMAIN = b"InterceptorRepository/v1\x00"
MAX_PAYLOAD = 512 * 1024
MAX_ENVELOPE = 768 * 1024
MAX_PACKAGE = 262_144
MAX_SOURCE = 131_072
MAX_CONFIG = 8_192
MAX_DEPTH = 64
MAX_PLUGINS = 100
MAX_SEQUENCE = 9_007_199_254_740_991
CLOCK_SKEW = 300
MAX_LIFETIME = 90 * 86_400
PUBLISH_LIFETIME = 30 * 86_400
MIN_LIVE_REMAINING = 14 * 86_400
FETCH_DEADLINE = 15
RUN_TIMEOUT = 20
_SEGMENT_RE = re.compile(r"^[0-9A-Za-z._-]{1,128}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_PUBLIC_DIRECTORIES = ("public", "www", "htdocs", "_site")


# ---------------------------------------------------------------- strict JSON (mirror of StrictJSON)

def _no_duplicates(pairs):
    out, seen = {}, set()
    for key, value in pairs:
        normalized = unicodedata.normalize("NFC", key)
        if normalized in seen:
            raise ToolError("invalid JSON: duplicate key")
        seen.add(normalized)
        out[key] = value
    return out


def _reject_constant(name):
    raise ToolError("invalid JSON: non-finite number")


def _parse_int(text):
    value = int(text)
    if abs(value) > MAX_SEQUENCE:
        raise ToolError("invalid JSON: integer out of range")
    return value


def _parse_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ToolError("invalid JSON: non-finite number")
    return value


def _check_shape(root):
    """Depth <= 64 and no lone surrogates anywhere (iterative, so hostile nesting cannot recurse)."""
    stack = [(root, 1)]
    while stack:
        value, depth = stack.pop()
        if isinstance(value, str):
            if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
                raise ToolError("invalid JSON: unpaired surrogate")
        elif isinstance(value, dict):
            if depth > MAX_DEPTH:
                raise ToolError("invalid JSON: nesting too deep")
            for key, item in value.items():
                stack.append((key, depth))
                stack.append((item, depth + 1))
        elif isinstance(value, list):
            if depth > MAX_DEPTH:
                raise ToolError("invalid JSON: nesting too deep")
            stack.extend((item, depth + 1) for item in value)


def strict_json(data):
    if data[:3] == b"\xef\xbb\xbf":
        raise ToolError("invalid JSON: byte order mark")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicates, parse_constant=_reject_constant,
                           parse_int=_parse_int, parse_float=_parse_float)
    except ToolError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ToolError("invalid JSON")
    _check_shape(value)
    return value


def _escape(text):
    out = ['"']
    for char in text:
        code = ord(char)
        if char in '"\\':
            out.append("\\" + char)
        elif char in "\b\t\n\f\r":
            out.append({"\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}[char])
        elif code < 0x20:
            out.append("\\u%04x" % code)
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def canonical(value):
    """Compact JSON, keys sorted by UTF-8 bytes, only quote/backslash/control characters escaped."""
    if value is None:
        return b"null"
    if value is True:
        return b"true"
    if value is False:
        return b"false"
    if isinstance(value, int):
        return str(value).encode()
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ToolError("cannot encode a non-finite number")
        return repr(value).encode()
    if isinstance(value, str):
        return _escape(value).encode("utf-8")
    if isinstance(value, list):
        return b"[" + b",".join(canonical(item) for item in value) + b"]"
    if isinstance(value, dict):
        keys = sorted(value, key=lambda key: key.encode("utf-8"))
        return b"{" + b",".join(canonical(key) + b":" + canonical(value[key]) for key in keys) + b"}"
    raise ToolError("cannot encode value")


def same_json(a, b):
    """Type-strict equality: 1, 1.0 and true are three different values, as in the app."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same_json(a[key], b[key]) for key in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same_json(x, y) for x, y in zip(a, b))
    return a == b


# ---------------------------------------------------------------- encodings and time

def strict_base64(text):
    if not isinstance(text, str) or len(text) % 4 != 0 or not text.isascii():
        raise ToolError("invalid base64")
    try:
        data = base64.b64decode(text, validate=True)
    except ValueError:
        raise ToolError("invalid base64")
    if base64.b64encode(data).decode() != text:
        raise ToolError("invalid base64")
    return data


def format_time(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


# ---------------------------------------------------------------- files and keys

def directory_names(path, suffix):
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise ToolError(f"{path}: not a real directory")
    if not stat.S_ISDIR(info.st_mode):
        raise ToolError(f"{path}: not a real directory")
    names = []
    for name in sorted(os.listdir(path)):
        if not name.endswith(suffix) or name.startswith("."):
            raise ToolError(f"unexpected entry {name} in {path}")
        names.append(name[: -len(suffix)])
    return names


def checked_key_path(path):
    """Resolve the parent; refuse Git checkouts and public/web directories above the key."""
    path = Path(path)
    if path.name in ("", ".", ".."):
        raise ToolError("invalid key path")
    try:
        parent = path.parent.resolve(strict=True)
    except OSError:
        raise ToolError("key directory does not exist")
    directory = parent
    while True:
        if os.path.lexists(directory / ".git"):
            raise ToolError("key path is inside a Git checkout")
        if directory.name.lower() in _PUBLIC_DIRECTORIES:
            raise ToolError("key path is inside a public directory")
        if directory.parent == directory:
            break
        directory = directory.parent
    return parent / path.name


def read_seed(path):
    """Owner-only (0600), regular, non-symlink, exactly 32 bytes."""
    target = checked_key_path(path)
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as error:
        raise ToolError(f"cannot open key: {error.strerror}")
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ToolError("key is not a regular file")
        if info.st_uid != os.geteuid():
            raise ToolError("key must be owned by the current user")
        if stat.S_IMODE(info.st_mode) != 0o600:
            raise ToolError("key permissions must be exactly 0600")
        seed = handle.read(33)
    if len(seed) != 32:
        raise ToolError("key must be exactly 32 raw bytes")
    return seed


def _runtime():
    for name in ("bun", "node"):
        found = shutil.which(name)
        if found:
            return found
    raise ToolError("Bun or Node.js is required for Ed25519 signing")


def _signing(command, payload):
    try:
        proc = subprocess.run([_runtime(), str(SIGNING), command], input=payload, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise ToolError("signing helper failed")
    return proc.returncode, proc.stdout.decode("ascii", "replace").strip()


def public_key(seed):
    code, out = _signing("public", seed)
    if code != 0 or not re.fullmatch(r"[0-9a-f]{64}", out):
        raise ToolError("signing helper failed")
    return bytes.fromhex(out)


def sign(seed, message):
    code, out = _signing("sign", seed + message)
    if code != 0 or not re.fullmatch(r"[0-9a-f]{128}", out):
        raise ToolError("signing helper failed")
    return bytes.fromhex(out)


def signature_valid(key, signature, message):
    code, out = _signing("verify", key + signature + message)
    return code == 0 and out == "1"


def fingerprint_of(raw_public):
    return hashlib.sha256(raw_public).hexdigest()


def write_exclusive(path, data, mode):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def keygen(path):
    target = checked_key_path(path)
    seed = os.urandom(32)
    fingerprint = fingerprint_of(public_key(seed))
    try:
        write_exclusive(target, seed, 0o600)
    except FileExistsError:
        raise ToolError("key already exists; refusing to overwrite")
    except OSError as error:
        raise ToolError(f"cannot create key: {error.strerror}")
    return fingerprint


# ---------------------------------------------------------------- packages and envelope

def validate_package(data, entry=None, what="package"):
    if entry is not None:
        if len(data) != entry["size"]:
            raise ToolError(f"{what}: size mismatch")
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ToolError(f"{what}: hash mismatch")
    if not data or len(data) > MAX_PACKAGE:
        raise ToolError(f"{what}: empty or larger than {MAX_PACKAGE} bytes")
    package = strict_json(data)
    if not isinstance(package, dict) or not isinstance(package.get('manifest'), dict):
        raise ToolError(f'{what}: invalid package')
    manifest = package['manifest']
    validate_manifest(manifest, what)
    if manifest['schemaVersion'] == 2:
        from repository_config import validate_source_files
        require_exact_keys(package, ('manifest', 'sourceFiles'), what)
        validate_source_files(manifest, package['sourceFiles'], what)
    else:
        require_exact_keys(package, ('manifest', 'source'), what)
        if not isinstance(package['source'], str) or len(package['source'].encode('utf-8')) > MAX_SOURCE:
            raise ToolError(f'{what}: invalid source')
    stack = [(manifest["settings"], 1)]
    while stack:
        value, depth = stack.pop()
        if isinstance(value, (dict, list)):
            if depth > 16:
                raise ToolError(f"{what}: settings nesting exceeds 16")
            children = value.values() if isinstance(value, dict) else value
            stack.extend((child, depth + 1) for child in children)
    if len(canonical(manifest["settings"])) > 8192:
        raise ToolError(f"{what}: settings exceed 8192 bytes")
    if entry is not None and (manifest["id"].upper() != entry["id"] or manifest["name"] != entry["name"]
                              or manifest["version"] != entry["version"]
                              or any(key in entry and (key not in manifest or entry[key] != manifest[key])
                                     for key in DISPLAY_METADATA_KEYS)):
        raise ToolError(f"{what}: metadata does not match the feed")
    return package


def valid_relative_path(path):
    return (isinstance(path, str) and len(path.encode("utf-8")) <= 256
            and all(_SEGMENT_RE.fullmatch(part) and part not in (".", "..") for part in path.split("/")))


def _field_uuid(value, what):
    if not isinstance(value, str) or not UUID_RE.fullmatch(value):
        raise ToolError(f"{what}: invalid UUID")
    return value.upper()


def parse_index(value):
    require_exact_keys(value, ("schemaVersion", "id", "name", "sequence", "issuedAt", "expiresAt", "plugins"), "index")
    if not is_int(value["schemaVersion"]) or value["schemaVersion"] != 1:
        raise ToolError("index: unsupported schemaVersion")
    sequence = value["sequence"]
    issued, expires = parse_time(value["issuedAt"]), parse_time(value["expiresAt"])
    if (not is_display_name(value["name"]) or not is_int(sequence) or not 1 <= sequence <= MAX_SEQUENCE
            or issued is None or expires is None):
        raise ToolError("index: invalid field")
    plugins = value["plugins"]
    if not isinstance(plugins, list):
        raise ToolError("index: plugins must be an array")
    if len(plugins) > MAX_PLUGINS:
        raise ToolError("index: too many plugins")
    entries, seen = [], set()
    for item in plugins:
        optional = tuple(key for key in DISPLAY_METADATA_KEYS if isinstance(item, dict) and key in item)
        require_exact_keys(item, ("id", "name", "version", "packagePath", "sha256", "size") + optional, "index plugin")
        validate_display_metadata(item, "index plugin")
        identifier = _field_uuid(item["id"], "index plugin id")
        size = item["size"]
        version = item["version"]
        if (not is_display_name(item["name"]) or not is_int(size) or not 1 <= size <= MAX_PACKAGE
                or not valid_relative_path(item["packagePath"]) or not isinstance(item["sha256"], str)
                or not _SHA_RE.fullmatch(item["sha256"]) or identifier in seen
                or not isinstance(version, str) or len(version) > 64 or not _SEMVER.fullmatch(version)):
            raise ToolError("index: invalid plugin entry")
        seen.add(identifier)
        entries.append({"id": identifier, "name": item["name"], "version": version,
                        "packagePath": item["packagePath"], "sha256": item["sha256"], "size": size,
                        **{key: item[key] for key in optional}})
    return {"id": _field_uuid(value["id"], "index id"), "name": value["name"], "sequence": sequence,
            "issuedAt": issued, "expiresAt": expires, "plugins": entries}


def verify_structure(envelope):
    """Everything except wall-clock checks. Returns a snapshot dict."""
    if len(envelope) > MAX_ENVELOPE:
        raise ToolError("envelope too large")
    top = strict_json(envelope)
    if not isinstance(top, dict) or not {"schemaVersion", "payload"} <= set(top) \
            or not set(top) <= {"schemaVersion", "payload", "signature"}:
        raise ToolError("envelope: expected schemaVersion, payload and optional signature")
    if not is_int(top["schemaVersion"]) or top["schemaVersion"] != 1:
        raise ToolError("envelope: unsupported schemaVersion")
    payload = strict_base64(top["payload"])
    if len(payload) > MAX_PAYLOAD:
        raise ToolError("payload too large")
    key = None
    if "signature" in top:
        sig = top["signature"]
        if not isinstance(sig, dict) or set(sig) != {"algorithm", "publicKey", "value"} or sig["algorithm"] != "ed25519":
            raise ToolError("invalid signature")
        try:
            raw, value = strict_base64(sig["publicKey"]), strict_base64(sig["value"])
        except ToolError:
            raise ToolError("invalid signature")
        if len(raw) != 32 or len(value) != 64 or not signature_valid(raw, value, SIGNATURE_DOMAIN + payload):
            raise ToolError("invalid signature")
        key = fingerprint_of(raw)
    return {"index": parse_index(strict_json(payload)), "fingerprint": key}


def check_time(index, now):
    if not index["expiresAt"] > now:
        raise ToolError("feed has expired")
    if not index["issuedAt"] <= now + CLOCK_SKEW:
        raise ToolError("feed is not yet valid")
    lifetime = index["expiresAt"] - index["issuedAt"]
    if lifetime <= 0:
        raise ToolError("feed lifetime is not positive")
    if lifetime > MAX_LIFETIME:
        raise ToolError("feed lifetime exceeds 90 days")


def verify_envelope(envelope, now):
    snapshot = verify_structure(envelope)
    check_time(snapshot["index"], now)
    return snapshot


def build_envelope(entries, repository_id, name, sequence, issued, seed=None):
    payload = canonical({"schemaVersion": 1, "id": repository_id, "name": name, "sequence": sequence,
                         "issuedAt": format_time(issued), "expiresAt": format_time(issued + PUBLISH_LIFETIME),
                         "plugins": entries})
    envelope = {"schemaVersion": 1, "payload": base64.b64encode(payload).decode()}
    if seed is not None:
        envelope["signature"] = {"algorithm": "ed25519", "publicKey": base64.b64encode(public_key(seed)).decode(),
                                 "value": base64.b64encode(sign(seed, SIGNATURE_DOMAIN + payload)).decode()}
    return canonical(envelope)


# ---------------------------------------------------------------- repository config

def load_configuration(root):
    root = Path(root)
    config = load_config(root)
    from repository_config import load_manifests
    ids = {manifest['id'].upper() for _, manifest in load_manifests(root)}
    if not ids:
        raise ToolError("no manifests")
    return {"id": check_uuid(config["id"], "id"), "url": config["repositoryURL"],
            "fingerprint": config["publicKeyFingerprint"], "plugins": ids}


def check_identity(snapshot, config, require_signed):
    if snapshot["index"]["id"] != config["id"]:
        raise ToolError("repository id does not match repository-config.json")
    if snapshot["fingerprint"] is not None:
        if config["fingerprint"] is None:
            raise ToolError("signed feed but no publicKeyFingerprint configured")
        if snapshot["fingerprint"] != config["fingerprint"]:
            raise ToolError(f"signing key fingerprint {snapshot['fingerprint']} does not match the configured fingerprint")
    elif require_signed:
        raise ToolError("feed is unsigned but a signature is required")


def check_plugin_set(snapshot, config):
    ids = [entry["id"] for entry in snapshot["index"]["plugins"]]
    if set(ids) != config["plugins"] or len(ids) != len(config["plugins"]):
        raise ToolError("feed plugin ids do not match authored plugin metadata")


def summary(snapshot):
    index = snapshot["index"]
    return canonical({"sequence": index["sequence"], "repositoryId": index["id"], "plugins": len(index["plugins"]),
                      "signed": snapshot["fingerprint"] is not None, "fingerprint": snapshot["fingerprint"]}).decode()


def package_url(feed_url, path):
    if not valid_relative_path(path):
        raise ToolError("invalid package path")
    url = feed_url.rsplit("/", 1)[0] + "/" + path
    if len(url) > 1024:
        raise ToolError("package URL too long")
    return url


# ---------------------------------------------------------------- publish

def is_package_filename(name):
    return (name.endswith(".json") and len(name.encode("utf-8")) <= 128 and not name.startswith(".")
            and re.fullmatch(r"[0-9A-Za-z._-]+", name) is not None)


def publish(directory, repository_id, name, sequence, key_path, now=None):
    root = Path(directory).resolve()
    seed = None
    if key_path is not None:
        resolved = checked_key_path(key_path)
        if resolved == root or root in resolved.parents:
            raise ToolError("key must be outside the published directory")
        seed = read_seed(resolved)
    plugins = root / "plugins"
    if not plugins.is_dir() or plugins.is_symlink():
        raise ToolError("plugins/ must be a real directory")
    files = sorted(os.listdir(plugins))
    if len(files) > MAX_PLUGINS:
        raise ToolError(f"more than {MAX_PLUGINS} packages")
    if not all(is_package_filename(file) for file in files):
        raise ToolError("plugins/ may contain only NAME.json files ([A-Za-z0-9._-])")
    entries, ids, packages = [], set(), {}
    for file in files:
        data = read_regular(plugins / file, MAX_PACKAGE)
        manifest = validate_package(data, what=f"plugins/{file}")["manifest"]
        identifier = manifest["id"].upper()
        if identifier in ids:
            raise ToolError(f"duplicate plugin id {identifier}")
        ids.add(identifier)
        packages[f"plugins/{file}"] = data
        entries.append({"id": identifier, "name": manifest["name"], "version": manifest["version"],
                        "packagePath": f"plugins/{file}", "sha256": hashlib.sha256(data).hexdigest(),
                        "size": len(data), **{key: manifest[key] for key in DISPLAY_METADATA_KEYS if key in manifest}})
    issued = int(time.time() if now is None else now)
    data = build_envelope(entries, repository_id, name, sequence, issued, seed)
    snapshot = verify_envelope(data, issued)
    for entry in snapshot["index"]["plugins"]:
        validate_package(packages[entry["packagePath"]], entry, entry["packagePath"])

    output = root / "repository.json"
    if os.path.lexists(output) and not stat.S_ISREG(os.lstat(output).st_mode):
        raise ToolError("repository.json exists and is not a regular file")
    temporary = root / f".repository-{uuid.uuid4()}.tmp"
    try:
        write_exclusive(temporary, data, 0o644)
        os.replace(temporary, output)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    if read_regular(output, MAX_ENVELOPE) != data:
        raise ToolError("repository.json changed after writing")
    verify_envelope(data, issued)
    lines = [f"wrote {output} (sequence {sequence}, {len(entries)} plugins, {'signed' if seed else 'unsigned'})"]
    if seed is not None:
        lines.append(f"fingerprint {fingerprint_of(public_key(seed))}")
    return lines


# ---------------------------------------------------------------- verify-local / previous / verify-live

def verify_local(root, directory, signed, now=None):
    config = load_configuration(root)
    if signed and config["fingerprint"] is None:
        raise ToolError("--signed requires publicKeyFingerprint in repository-config.json")
    directory = Path(directory)
    envelope = read_regular(directory / "repository.json", MAX_ENVELOPE)
    snapshot = verify_envelope(envelope, time.time() if now is None else now)
    check_identity(snapshot, config, signed)
    check_plugin_set(snapshot, config)
    on_disk = {f"plugins/{name}.json" for name in directory_names(directory / "plugins", ".json")}
    if on_disk != {entry["packagePath"] for entry in snapshot["index"]["plugins"]}:
        raise ToolError("plugins/ does not match the feed")
    for entry in snapshot["index"]["plugins"]:
        validate_package(read_regular(directory / entry["packagePath"], MAX_PACKAGE), entry, entry["packagePath"])
    return summary(snapshot)


def previous(root, file, now=None):
    config = load_configuration(root)
    if config["fingerprint"] is None:
        raise ToolError("previous requires publicKeyFingerprint in repository-config.json")
    envelope = read_regular(file, MAX_ENVELOPE)
    # Untrusted pre-parse, used only to choose the verification time; every trusted value comes from verification.
    try:
        top = strict_json(envelope)
        issued = parse_time(strict_json(strict_base64(top["payload"]))["issuedAt"])
    except (ToolError, KeyError, TypeError):
        issued = None
    if issued is None:
        raise ToolError("previous feed: cannot read issuedAt")
    if issued > (time.time() if now is None else now) + CLOCK_SKEW:
        raise ToolError("previous feed was issued in the future")
    snapshot = verify_envelope(envelope, issued)
    check_identity(snapshot, config, True)
    return str(snapshot["index"]["sequence"])


def _fetch(url, limit, temporary):
    output = Path(temporary) / "download"
    saved = fetch_previous.MAX_BYTES
    fetch_previous.MAX_BYTES = limit
    try:
        fetch_previous.download(url, output, FETCH_DEADLINE)
    except urllib.error.HTTPError as error:
        raise ToolError(f"{url}: HTTP {error.code}; redirects are refused")
    except (OSError, ValueError, urllib.error.URLError) as error:
        raise ToolError(f"{url}: fetch failed: {error}")
    finally:
        fetch_previous.MAX_BYTES = saved
    return output.read_bytes()


def verify_live(root, sequence, now=None):
    config = load_configuration(root)
    if config["fingerprint"] is None:
        raise ToolError("verify-live requires publicKeyFingerprint in repository-config.json")
    now = time.time() if now is None else now
    with tempfile.TemporaryDirectory(prefix="interceptor-live-") as temporary:
        snapshot = verify_envelope(_fetch(config["url"], MAX_ENVELOPE, temporary), now)
        check_identity(snapshot, config, True)
        check_plugin_set(snapshot, config)
        index = snapshot["index"]
        if index["sequence"] != sequence:
            raise ToolError(f"live sequence {index['sequence']} is not the expected {sequence}")
        if index["expiresAt"] - now < MIN_LIVE_REMAINING:
            raise ToolError("live feed expires in less than 14 days")
        for entry in index["plugins"]:
            data = _fetch(package_url(config["url"], entry["packagePath"]), min(entry["size"], MAX_PACKAGE), temporary)
            validate_package(data, entry, entry["packagePath"])
    return summary(snapshot)


# ---------------------------------------------------------------- samples

def simulator_binary():
    candidates = []
    if os.environ.get("INTERCEPTOR_SIMULATOR"):
        candidates.append(Path(os.environ["INTERCEPTOR_SIMULATOR"]))
    candidates.append(HERE.parent / ".tools" / "bin" / "interceptor-simulator")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise ToolError("interceptor-simulator not found; run tools/build-runtime.sh")


_PHASE_NAMES = ("request.onEnter", "request.onLeave", "response.onEnter", "response.onLeave")


def run_hook(binary, directory, source, hook, event, config, package=None):
    """Run legacy source or a complete schema 2 package using private temporary input files."""
    files = [("event.json", event), ("config.json", config)]
    input_name = "package.json" if package is not None else "source.js"
    files.append((input_name, package if package is not None else source))
    paths = {}
    for name, data in files:
        paths[name] = Path(directory) / name
        paths[name].write_bytes(data)
    command = [str(binary), "run-package" if package is not None else "run", str(paths[input_name]), hook,
               str(paths["event.json"]), str(paths["config.json"])]
    try:
        proc = subprocess.run(command, capture_output=True, timeout=RUN_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as error:
        raise ToolError(f"simulator failed to run: {error}")
    return proc.returncode, proc.stdout


def _case_route(case, package, index):
    """(hook argument, full package bytes or None). Schema 2 uses phase; schema 1 retains legacy hook."""
    version = package["manifest"]["schemaVersion"]
    if version == 2:
        if "hook" in case or case.get("phase") not in _PHASE_NAMES:
            raise ToolError(f"fixtures/cases.json[{index}]: schema 2 cases need a lifecycle phase and no hook")
        return case["phase"], canonical(package)
    if "phase" in case or case.get("hook") not in ("request", "response"):
        raise ToolError(f"fixtures/cases.json[{index}]: schema 1 compatibility cases need hook request|response")
    return ("onRequest" if case["hook"] == "request" else "onResponse"), None


def _judge(case, code, output, failures):
    """Compare one simulator run with expected / expectError; shared by the schema 2 samples and the v1 legacy suite."""
    name = case["name"]
    if code == 0:
        if "expectError" in case:
            failures.append(f"{name}: expected {case['expectError']}, got result {output.decode('utf-8', 'replace').strip()}")
            return
        try:
            actual = strict_json(output)
        except ToolError:
            failures.append(f"{name}: simulator printed invalid JSON")
            return
        if not same_json(actual, case["expected"]):
            failures.append(f"{name}: expected {canonical(case['expected']).decode()}, got {canonical(actual).decode()}")
    elif code in (4, 6):
        error = {4: "invalidInput", 6: "scriptError"}[code]
        if case.get("expectError") != error:
            failures.append(f"{name}: unexpected {error}")
    else:
        raise ToolError(f"{name}: simulator exited with status {code}")


def legacy_samples(root):
    """Run the preserved schema 1 conformance cases (fixtures/legacy-v1) on the common engine via the legacy route."""
    root = Path(root)
    base = root / "fixtures" / "legacy-v1"
    config_json = read_regular(root / "fixtures" / "config.json", MAX_CONFIG)
    cases = strict_json(read_regular(base / "cases.json"))
    if not isinstance(cases, list) or not cases:
        raise ToolError("fixtures/legacy-v1/cases.json: expected a non-empty array")
    binary = simulator_binary()
    sources, failures = {}, []
    with tempfile.TemporaryDirectory(prefix="interceptor-legacy-") as temporary:
        for index, case in enumerate(cases):
            if not (isinstance(case, dict) and isinstance(case.get("name"), str) and isinstance(case.get("event"), dict)
                    and case.get("hook") in ("request", "response") and "phase" not in case
                    and ("expected" in case) != ("expectError" in case)
                    and re.fullmatch(r"[a-z0-9-]+", str(case.get("plugin")))):
                raise ToolError(f"fixtures/legacy-v1/cases.json[{index}]: invalid case")
            plugin = case["plugin"]
            if plugin not in sources:
                sources[plugin] = read_regular(base / "src" / f"{plugin}.js", MAX_SOURCE)
                manifest = strict_json(read_regular(base / "manifests" / f"{plugin}.json"))
                validate_manifest(manifest, f"fixtures/legacy-v1/manifests/{plugin}.json")
                if manifest.get("schemaVersion") != 1:
                    raise ToolError(f"fixtures/legacy-v1/manifests/{plugin}.json: not schema 1")
            hook = "onRequest" if case["hook"] == "request" else "onResponse"
            code, output = run_hook(binary, temporary, sources[plugin], hook, canonical(case["event"]), config_json)
            _judge(case, code, output, failures)
    if failures:
        raise ToolError("legacy v1 cases failed:\n  " + "\n  ".join(failures))
    return f"legacy v1 samples ok: {len(cases)} cases, {len(sources)} sources"


def generated_sources(directory, root):
    """Read the exact generated source map, rejecting symlink ancestors and unexpected file types."""
    directory = Path(directory)
    for ancestor in (directory, *directory.parents):
        if ancestor.is_symlink():
            raise ToolError(f"generated scripts cross a symlink: {directory}")
        if ancestor == Path(root):
            break
    if not directory.is_dir():
        raise ToolError(f"generated scripts directory is missing: {directory}")
    result = {}
    def walk_error(error):
        raise ToolError(f"cannot read generated scripts: {error}")
    for current, dirs, files in os.walk(directory, followlinks=False, onerror=walk_error):
        for name in dirs:
            if (Path(current) / name).is_symlink():
                raise ToolError(f"symlink in generated scripts: {name}")
        for name in files:
            path = Path(current) / name
            try:
                result[path.relative_to(directory).as_posix()] = read_regular(path, MAX_SOURCE).decode("utf-8")
            except UnicodeDecodeError:
                raise ToolError(f"generated script is not UTF-8: {path}") from None
    return result


def samples(root, directory):
    root, directory = Path(root), Path(directory)
    config = load_configuration(root)
    config_json = read_regular(root / "fixtures" / "config.json", MAX_CONFIG)
    packages = {}
    for name in directory_names(directory / "plugins", ".json"):
        package = validate_package(read_regular(directory / "plugins" / f"{name}.json", MAX_PACKAGE), what=f"plugins/{name}.json")
        if package["manifest"]["schemaVersion"] == 2:
            script_directory = "build/scripts"
            scripts = generated_sources(root / script_directory / name, root)
            if package["sourceFiles"] != scripts:
                raise ToolError(f"plugins/{name}.json: sourceFiles differ from {script_directory}/{name}/")
        else:
            script_directory = "build/scripts" if (root / "src").exists() else "scripts"
            script = read_regular(root / script_directory / f"{name}.js", MAX_SOURCE)
            if package["source"].encode("utf-8") != script:
                raise ToolError(f"plugins/{name}.json: source differs from {script_directory}/{name}.js")
        packages[name] = package
    if {package["manifest"]["id"].upper() for package in packages.values()} != config["plugins"]:
        raise ToolError("packages do not match authored plugin metadata")
    cases = strict_json(read_regular(root / "fixtures" / "cases.json"))
    if not isinstance(cases, list) or not cases:
        raise ToolError("fixtures/cases.json: expected a non-empty array")
    binary = simulator_binary()
    covered, failures = set(), []
    with tempfile.TemporaryDirectory(prefix="interceptor-samples-") as temporary:
        for index, case in enumerate(cases):
            ok = (isinstance(case, dict) and isinstance(case.get("name"), str) and case.get("plugin") in packages
                  and isinstance(case.get("event"), dict))
            if not ok:
                raise ToolError(f"fixtures/cases.json[{index}]: invalid case")
            name = case["name"]
            has_expected, has_error = "expected" in case, "expectError" in case
            if has_expected == has_error or not set(case) <= {"name", "plugin", "hook", "phase", "event", "expected", "expectError"}:
                raise ToolError(f"fixtures/cases.json[{index}] {name}: needs exactly one of expected / expectError")
            package = packages[case["plugin"]]
            hook, routed_package = _case_route(case, package, index)
            covered.add(case["plugin"])
            code, output = run_hook(binary, temporary, package.get("source", "").encode("utf-8"), hook, canonical(case["event"]),
                                    config_json, package=routed_package)
            _judge(case, code, output, failures)
    if covered != set(packages):
        raise ToolError("fixtures/cases.json does not cover every package")
    if failures:
        raise ToolError("sample cases failed:\n  " + "\n  ".join(failures))
    return f"samples ok: {len(cases)} cases, {len(packages)} packages"


# ---------------------------------------------------------------- command line

USAGE = __doc__


def _sequence(text):
    if not isinstance(text, str) or not text.isascii() or not text.isdecimal() or not 1 <= int(text) <= MAX_SEQUENCE:
        raise UsageError(f"SEQUENCE must be 1...{MAX_SEQUENCE}")
    return int(text)


def main(argv):
    command, args = (argv[0], argv[1:]) if argv else (None, [])
    if command in ("--help", "-h") and not args:
        print(USAGE, end="")
    elif command == "keygen" and len(args) == 1:
        print(keygen(args[0]))
    elif command == "fingerprint" and len(args) == 1:
        print(fingerprint_of(public_key(read_seed(args[0]))))
    elif command == "publish" and len(args) >= 1:
        options = parse_args(args[1:], ("--id", "--name", "--sequence", "--key"), flags=("--key",))
        if not is_display_name(options["--name"]):
            raise UsageError("invalid --name")
        identifier = check_uuid(options["--id"], "--id")
        for line in publish(args[0], identifier, options["--name"], _sequence(options["--sequence"]), options.get("--key")):
            print(line)
    elif command == "samples" and len(args) == 2:
        print(samples(args[0], args[1]))
    elif command == "legacy-samples" and len(args) == 1:
        print(legacy_samples(args[0]))
    elif command == "verify-local" and len(args) == 2:
        print(verify_local(args[0], args[1], False))
    elif command == "verify-local" and len(args) == 3 and args[2] == "--signed":
        print(verify_local(args[0], args[1], True))
    elif command == "previous" and len(args) == 2:
        print(previous(args[0], args[1]))
    elif command == "verify-live" and len(args) == 2:
        print(verify_live(args[0], _sequence(args[1])))
    else:
        raise UsageError("unknown or incomplete command\n" + USAGE)


if __name__ == "__main__":
    run_main(main)
