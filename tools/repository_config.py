"""Shared, standard-library-only helpers for build.py, configure.py and guard.py.

Everything here is strict and fails closed: duplicate JSON keys, symlinks, unknown fields and
malformed values are errors. No network access, no keys.
"""
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import unicodedata
import uuid
from pathlib import Path

OFFICIAL_REPOSITORY = "qtmleap/Interceptor-Plugins"
BASELINE_IDS = ("90A213C0-9D3C-47F5-ABB8-C15C7472E2AD", "76532D8C-608A-4EA3-AC16-755BABF2AB7E",
                "5B478646-4A70-4EF1-B04B-6CB63450E5A4")
BASELINE_URLS = ("https://qtmleap.github.io/Interceptor-Plugins/repository.json",)
MAX_SOURCE_BYTES = 131_072
MAX_PACKAGE_BYTES = 262_144
MAX_FILE_BYTES = 1_048_576

UUID_RE = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
REPO_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
SAMPLE_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CONFIG_KEYS = ("schemaVersion", "id", "name", "githubRepository", "repositoryURL", "publicKeyFingerprint",
               "upstreamRevision")


class ToolError(Exception):
    """A diagnosable failure; main() prints it concisely and exits 1."""


class UsageError(ToolError):
    pass


def run_main(function):
    try:
        function(sys.argv[1:])
    except UsageError as error:
        sys.stderr.write(f"error: {error}\n")
        sys.exit(2)
    except ToolError as error:
        sys.stderr.write(f"error: {error}\n")
        sys.exit(1)
    except OSError as error:
        sys.stderr.write(f"error: {error.strerror or error}: {getattr(error, 'filename', '') or ''}\n")
        sys.exit(1)
    except Exception as error:  # never leak a traceback or a partial result
        sys.stderr.write(f"error: unexpected {type(error).__name__}: {error}\n")
        sys.exit(1)


def parse_args(argv, options, flags=()):
    """Strict `--name value` parser: unknown, duplicate, missing-value and positional arguments are errors."""
    values = {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg not in options:
            raise UsageError(f"unknown or unexpected argument: {arg}")
        if arg in values:
            raise UsageError(f"duplicate argument: {arg}")
        if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
            raise UsageError(f"missing value for {arg}")
        values[arg] = argv[i + 1]
        i += 2
    for required in options:
        if required not in values and required not in flags:
            raise UsageError(f"missing required argument: {required}")
    return values


# ---------------------------------------------------------------- strict JSON / files

def _no_duplicates(pairs):
    out, seen = {}, set()
    for key, value in pairs:
        normalized = unicodedata.normalize("NFC", key)
        if normalized in seen:
            raise ToolError("duplicate JSON key")
        seen.add(normalized)
        out[key] = value
    return out


def _reject_constant(name):
    raise ToolError(f"invalid JSON number: {name}")


def _safe_integer(text):
    value = int(text)
    if not -9_007_199_254_740_991 <= value <= 9_007_199_254_740_991:
        raise ToolError("JSON integer out of range")
    return value


def _finite_number(text):
    value = float(text)
    if not math.isfinite(value):
        raise ToolError("invalid JSON number")
    return value


def _json_shape(value, maximum=64):
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in item):
                raise ToolError("invalid JSON surrogate")
        elif isinstance(item, (dict, list)):
            if depth > maximum:
                raise ToolError("JSON nesting limit exceeded")
            if isinstance(item, dict):
                stack.extend((key, depth) for key in item)
                stack.extend((child, depth + 1) for child in item.values())
            else:
                stack.extend((child, depth + 1) for child in item)


def read_regular(path, limit=MAX_FILE_BYTES):
    """Bytes of a regular, non-symlink file no larger than limit."""
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise ToolError(f"missing file: {path}")
    if stat.S_ISLNK(info.st_mode):
        raise ToolError(f"symlinks are not allowed: {path}")
    if not stat.S_ISREG(info.st_mode):
        raise ToolError(f"not a regular file: {path}")
    if info.st_size > limit:
        raise ToolError(f"file too large: {path}")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    with os.fdopen(fd, "rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ToolError(f"file too large: {path}")
    return data


def parse_json_object(data, what):
    try:
        text = data.decode("utf-8")
        value = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant,
                           parse_int=_safe_integer, parse_float=_finite_number)
        _json_shape(value)
    except ToolError as error:
        raise ToolError(f"{what}: {error}")
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ToolError(f"{what}: invalid JSON")
    if not isinstance(value, dict):
        raise ToolError(f"{what}: expected a JSON object")
    return value


def load_json(path, what):
    return parse_json_object(read_regular(path), what)


def dump_json(value):
    """Human-edited file format: 2-space indent, insertion order, trailing newline."""
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def require_exact_keys(obj, keys, what):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ToolError(f"{what}: expected exactly the fields {', '.join(keys)}")


# ---------------------------------------------------------------- value validators

def is_display_name(text, limit=80):
    if not isinstance(text, str) or not text or len(text) > limit or len(text.encode("utf-8", "replace")) > 256:
        return False
    return not any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp", "Cs") for c in text)


DISPLAY_METADATA_LIMITS = (("author", 80, 256), ("summary", 280, 1024), ("category", 80, 256))
DISPLAY_METADATA_KEYS = tuple(key for key, _, _ in DISPLAY_METADATA_LIMITS)
# Publisher-declared, manifest-only (never mirrored into the index): same grammar as the index timestamps.
PUBLISHED_AT_KEY = "publishedAt"
_TIME_RE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z$")


def parse_time(text):
    """Second-resolution UTC RFC 3339 (yyyy-MM-ddTHH:mm:ssZ) to epoch seconds, or None."""
    match = _TIME_RE.fullmatch(text) if isinstance(text, str) else None
    if not match:
        return None
    year, month, day, hour, minute, second = map(int, match.groups())
    if year < 1 or not 1 <= month <= 12 or hour > 23 or minute > 59 or second > 59:
        return None
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    if not 1 <= day <= days:
        return None
    return int(_epoch(year, month, day)) + hour * 3600 + minute * 60 + second


def _epoch(year, month, day):
    # Days from civil (proleptic Gregorian), matching the app's DateCodec.
    y = year - 1 if month <= 2 else year
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return (era * 146_097 + doe - 719_468) * 86_400


def validate_display_metadata(value, what):
    """Optional single-line publisher text; Python length counts Unicode scalars after surrogate rejection."""
    for key, max_chars, max_bytes in DISPLAY_METADATA_LIMITS:
        if key in value:
            text = value[key]
            if not isinstance(text, str) or not text.strip() or len(text) > max_chars \
                    or len(text.encode("utf-8", "replace")) > max_bytes \
                    or any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp", "Cs") for c in text):
                _fail(what, f"invalid {key}")


def validate_published_at(value, what):
    """Optional publisher-declared publication date; copied unchanged, never generated by tooling."""
    if PUBLISHED_AT_KEY in value and parse_time(value[PUBLISHED_AT_KEY]) is None:
        _fail(what, f"invalid {PUBLISHED_AT_KEY}")


def check_uuid(value, what):
    if not isinstance(value, str) or not UUID_RE.fullmatch(value):
        raise ToolError(f"{what}: not a UUID")
    return value.upper()


def check_repository(value, what="repository"):
    if not isinstance(value, str) or value.count("/") != 1:
        raise ToolError(f"{what}: expected OWNER/NAME")
    owner, name = value.split("/")
    if not OWNER_RE.fullmatch(owner) or not REPO_NAME_RE.fullmatch(name) or name in (".", "..") or name.endswith(".git"):
        raise ToolError(f"{what}: invalid OWNER/NAME")
    return value


def same_repository(a, b):
    return a.lower() == b.lower()


def check_fingerprint(value, what="fingerprint"):
    if not isinstance(value, str) or not FINGERPRINT_RE.fullmatch(value):
        raise ToolError(f"{what}: expected 64 lowercase hex characters")
    return value


_HOST_LABEL = re.compile(r"^[a-z0-9-]{1,63}$")
_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def canonical_url(text):
    """Mirror of the app's RepositoryURL canonical form (HTTPS DNS host, no query/userinfo/escapes)."""
    if not isinstance(text, str) or not text or len(text) > 2048:
        raise ToolError("url: invalid")
    if any(ord(c) <= 0x20 or ord(c) >= 0x7F or c in "%?#@\\" for c in text):
        raise ToolError("url: invalid characters")
    if text[:8].lower() != "https://":
        raise ToolError("url: must use https")
    rest = text[8:]
    slash = rest.find("/")
    authority, path = (rest, "") if slash < 0 else (rest[:slash], rest[slash:])
    host, port = authority, None
    if ":" in authority:
        host, port_text = authority.split(":", 1)
        if not port_text.isdigit() or len(port_text) > 5 or port_text[0] == "0" or not 1 <= int(port_text) <= 65535:
            raise ToolError("url: invalid port")
        port = None if int(port_text) == 443 else int(port_text)
    host = host.lower()
    labels = host.split(".")
    if (len(host) > 253 or (len(labels) < 2 and host != "localhost") or host.endswith(".")
            or any(not _HOST_LABEL.fullmatch(l) or l[0] == "-" or l[-1] == "-" for l in labels)
            or not "a" <= labels[-1][0] <= "z"):
        raise ToolError("url: invalid host")
    if path in ("", "/"):
        segments = ["repository.json"]
    else:
        segments = path[1:].split("/")
        if path.endswith("/"):
            segments[-1] = "repository.json"
    if any(not _SEGMENT.fullmatch(s) or s in (".", "..") for s in segments):
        raise ToolError("url: invalid path")
    result = "https://" + host + (f":{port}" if port else "") + "/" + "/".join(segments)
    if len(result) > 1024:
        raise ToolError("url: too long")
    return result


def url_is_reserved(url, reserved):
    """Equal to a reserved feed URL, or inside a reserved feed's directory (case-insensitive)."""
    lowered = url.lower()
    for item in reserved["urls"]:
        item = canonical_url(item).lower()
        namespace = item.rsplit("/", 1)[0]
        if lowered == item or lowered == namespace or lowered.startswith(namespace + "/"):
            return True
    return False


# ---------------------------------------------------------------- repository config / reserved identities

def load_config(root):
    config = load_json(Path(root) / "repository-config.json", "repository-config.json")
    return validate_config(config)


def validate_config(config):
    require_exact_keys(config, CONFIG_KEYS, "repository-config.json")
    if not is_int(config["schemaVersion"]) or config["schemaVersion"] != 1:
        raise ToolError("repository-config.json: unsupported schemaVersion")
    check_uuid(config["id"], "repository-config.json id")
    if not is_display_name(config["name"]):
        raise ToolError("repository-config.json: invalid name")
    check_repository(config["githubRepository"], "repository-config.json githubRepository")
    if canonical_url(config["repositoryURL"]) != config["repositoryURL"]:
        raise ToolError("repository-config.json: repositoryURL is not in canonical form")
    if config["publicKeyFingerprint"] is not None:
        check_fingerprint(config["publicKeyFingerprint"], "repository-config.json publicKeyFingerprint")
    if not isinstance(config["upstreamRevision"], str) or not REVISION_RE.fullmatch(config["upstreamRevision"]):
        raise ToolError("repository-config.json: upstreamRevision must be a 40-hex commit SHA")
    return config


def load_reserved(root):
    data = load_json(Path(root) / "tools" / "reserved.json", "tools/reserved.json")
    require_exact_keys(data, ("schemaVersion", "officialRepository", "ids", "urls", "fingerprints"), "tools/reserved.json")
    if not is_int(data["schemaVersion"]) or data["schemaVersion"] != 1:
        raise ToolError("tools/reserved.json: unsupported schemaVersion")
    if data["officialRepository"] != OFFICIAL_REPOSITORY:
        raise ToolError("tools/reserved.json: officialRepository must be " + OFFICIAL_REPOSITORY)
    for key in ("ids", "urls", "fingerprints"):
        if not isinstance(data[key], list):
            raise ToolError(f"tools/reserved.json: {key} must be an array")
    ids = [check_uuid(i, "tools/reserved.json ids") for i in data["ids"]]
    urls = [canonical_url(u) for u in data["urls"]]
    fingerprints = [check_fingerprint(f, "tools/reserved.json fingerprints") for f in data["fingerprints"]]
    if not set(BASELINE_IDS) <= set(ids) or not set(BASELINE_URLS) <= set(urls):
        raise ToolError("tools/reserved.json: official baseline identities were removed")
    return {"ids": ids, "urls": urls, "fingerprints": fingerprints}


# ---------------------------------------------------------------- samples

_HOST_MATCH_LABEL = re.compile(r"^[a-z0-9-]{1,63}$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})"
                     r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
                     r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")
_PHASES = ("request.headers", "request.completed", "response.headers", "response.completed")
_METADATA = ("method", "host", "status", "path")
_HEADER_NAME = re.compile(r"^[0-9A-Za-z!#$%&'*+.^_`|~-]{1,128}$")


def _fail(what, why):
    raise ToolError(f"{what}: {why}")


def _strings(value, what, minimum=0, maximum=32):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum or not all(isinstance(v, str) for v in value):
        _fail(what, "invalid string list")
    return value


def _host_ok(host):
    labels = host.split(".")
    return (0 < len(host) <= 253 and all(_HOST_MATCH_LABEL.fullmatch(l) and l[0] != "-" and l[-1] != "-" for l in labels))


def valid_source_path(value):
    return (isinstance(value, str) and len(value.encode('utf-8')) <= 256
            and all(re.fullmatch(r'[A-Za-z0-9._~-]+', part) and part not in ('.', '..')
                    for part in value.split('/')))


def hook_references(manifest):
    return {value for match in manifest['matches'] for leg in match['hooks'].values() for value in leg.values()}


def validate_source_files(manifest, files, what):
    if not isinstance(files, dict) or not 1 <= len(files) <= 64 or not all(valid_source_path(k) for k in files):
        _fail(what, 'invalid sourceFiles')
    if set(files) != hook_references(manifest):
        _fail(what, 'sourceFiles must exactly match manifest references')
    if not all(isinstance(v, str) and '\x00' not in v for v in files.values()):
        _fail(what, 'sourceFiles must contain JavaScript text without NUL')
    if sum(len(v.encode('utf-8')) for v in files.values()) > MAX_SOURCE_BYTES:
        _fail(what, 'combined JavaScript exceeds 128 KiB')


def _validate_match(match, what, allow_status, v2=False):
    required = {'hosts', 'methods', 'path', 'hooks'} if v2 else {'hosts'}
    allowed = required if v2 else {'hosts', 'methods', 'path', 'status'}
    if not isinstance(match, dict) or not required <= set(match) or not set(match) <= allowed:
        _fail(what, "invalid match")
    hosts = _strings(match["hosts"], what + " hosts", 1, 32)
    if len(set(hosts)) != len(hosts) or not all(_host_ok(h) for h in hosts):
        _fail(what, "invalid hosts")
    if v2 and len(hosts) != 1:
        _fail(what, 'a route requires one host')
    if "methods" in match:
        methods = _strings(match["methods"], what + " methods", 1, 16)
        if len(set(methods)) != len(methods) or not all(re.fullmatch(r"[A-Z]{1,16}", x) for x in methods):
            _fail(what, "invalid methods")
        if v2 and len(methods) != 1:
            _fail(what, 'a route requires one method')
    if "path" in match:
        path = match["path"]
        require_exact_keys(path, ("kind", "value"), what + " path")
        if path["kind"] not in ("exact", "prefix") or not isinstance(path["value"], str) \
                or not re.fullmatch(r"/(?:[A-Za-z0-9\-._~!$&'()*+,;=:@/]|%[0-9A-Fa-f]{2})*", path["value"]) \
                or len(path["value"]) > 1024:
            _fail(what, "invalid path match")
        if v2 and path['kind'] != 'exact':
            _fail(what, 'route paths must be exact')
    if "status" in match:
        status = match["status"]
        require_exact_keys(status, ("min", "max"), what + " status")
        if not allow_status or not is_int(status["min"]) or not is_int(status["max"]) \
                or not 100 <= status["min"] <= status["max"] <= 599:
            _fail(what, "invalid status range")
    if v2:
        hooks = match['hooks']
        if not isinstance(hooks, dict) or not hooks or not set(hooks) <= {'request', 'response'}:
            _fail(what, 'invalid hooks')
        for callbacks in hooks.values():
            if not isinstance(callbacks, dict) or not callbacks or not set(callbacks) <= {'onEnter', 'onLeave'} \
                    or not all(valid_source_path(file) for file in callbacks.values()):
                _fail(what, 'invalid hook file references')


def _validate_read(read, what, schema_version, headers_phase):
    require_exact_keys(read, ("metadata", "headers", "queryKeys", "body"), what + " read")
    metadata = _strings(read["metadata"], what + " metadata", 0, 4)
    if len(set(metadata)) != len(metadata) or not set(metadata) <= set(_METADATA):
        _fail(what, "invalid metadata")
    headers = _strings(read["headers"], what + " headers", 0, 32)
    if len({h.lower() for h in headers}) != len(headers) or not all(_HEADER_NAME.fullmatch(h) for h in headers):
        _fail(what, "invalid headers")
    query = _strings(read["queryKeys"], what + " queryKeys", 0, 32)
    if len(set(query)) != len(query) or not all(0 < len(k.encode()) <= 128 and not any(ord(c) < 0x20 or ord(c) == 0x7F for c in k) for k in query):
        _fail(what, "invalid queryKeys")
    body = read["body"]
    if not isinstance(body, dict) or "mode" not in body or not set(body) <= {"mode", "pointers"}:
        _fail(what, "invalid body")
    if body["mode"] == "none" or (body["mode"] == "raw" and schema_version == 1):
        if "pointers" in body:
            _fail(what, "pointers not allowed")
    elif body["mode"] == "json" and schema_version == 2:
        if "pointers" in body:
            _fail(what, "pointers not allowed")
    elif body["mode"] == "jsonPointers" and schema_version == 1:
        pointers = _strings(body.get("pointers"), what + " pointers", 1, 32)
        if len(set(pointers)) != len(pointers) or not all(
                len(p) <= 256 and (p == "" or (p[0] == "/" and not re.search(r"~(?![01])", p))) for p in pointers):
            _fail(what, "invalid pointers")
    else:
        _fail(what, "invalid body mode")
    if headers_phase and body["mode"] != "none":
        _fail(what, "header phases cannot read the body")


def validate_manifest(m, what):
    """Mirror of the PluginManifest rules the app enforces (the Swift driver re-validates with production code).

    Schema 1 is the legacy dry-run shape; schema 2 declares `matches` and `write` for the HTTP lifecycle hooks.
    """
    version = m.get("schemaVersion") if isinstance(m, dict) else None
    if not is_int(version) or version not in (1, 2):
        if isinstance(m, dict) and "schemaVersion" in m:
            _fail(what, "unsupported schemaVersion")
    common = ("schemaVersion", "id", "name", "version")
    tail = ("read", "endpointBindings", "settings")
    optional = tuple(key for key in DISPLAY_METADATA_KEYS + (PUBLISHED_AT_KEY,) if isinstance(m, dict) and key in m)
    if version == 2:
        require_exact_keys(m, common + ("matches", "read", "write", "endpointBindings", "settings") + optional, what)
    else:
        require_exact_keys(m, common + ("subscriptions",) + tail + optional, what)
    validate_display_metadata(m, what)
    validate_published_at(m, what)
    check_uuid(m["id"], f"{what} id")
    if not is_display_name(m["name"]):
        _fail(what, "invalid name")
    if not isinstance(m["version"], str) or len(m["version"]) > 64 or not _SEMVER.fullmatch(m["version"]):
        _fail(what, "version must be SemVer")
    headers_phase = False
    if version == 2:
        matches = m["matches"]
        if not isinstance(matches, list) or not 1 <= len(matches) <= 16:
            _fail(what, "1 to 16 matches required")
        for match in matches:
            _validate_match(match, what, False, v2=True)
        write = m["write"]
        require_exact_keys(write, ("requestBody", "responseBody"), what + " write")
        if not all(isinstance(write[key], bool) for key in write):
            _fail(what, "write grants must be booleans")
    else:
        subs = m["subscriptions"]
        if not isinstance(subs, list) or not 1 <= len(subs) <= 8:
            _fail(what, "1 to 8 subscriptions required")
        for sub in subs:
            require_exact_keys(sub, ("phase", "match"), what + " subscription")
            if sub["phase"] not in _PHASES:
                _fail(what, "unknown phase")
            headers_phase = headers_phase or sub["phase"].endswith(".headers")
            _validate_match(sub["match"], what, sub["phase"].startswith("response."))
    _validate_read(m["read"], what, version, headers_phase)
    bindings = _strings(m["endpointBindings"], what + " endpointBindings", 0, 4)
    if len(set(bindings)) != len(bindings) or not all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", b) for b in bindings):
        _fail(what, "invalid endpointBindings")
    if not isinstance(m["settings"], dict) or len(json.dumps(m["settings"], ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()) > 8192:
        _fail(what, "invalid settings")
    _json_shape(m["settings"], 16)
    if version == 2 and len(json.dumps(m, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')) > 32768:
        _fail(what, 'manifest exceeds 32 KiB')


def _list_dir(directory, suffix, kind):
    info = os.lstat(directory) if os.path.lexists(directory) else None
    if info is None:
        raise ToolError(f"missing directory: {directory}")
    if not stat.S_ISDIR(info.st_mode):
        raise ToolError(f"{kind} must be a real directory (no symlinks): {directory}")
    names = {}
    for entry in sorted(os.listdir(directory)):
        if entry == ".DS_Store":
            continue
        if not entry.endswith(suffix):
            raise ToolError(f"unexpected file in {kind}/: {entry}")
        stem = entry[: -len(suffix)]
        if not SAMPLE_NAME_RE.fullmatch(stem) or len(stem) > 64:
            raise ToolError(f"invalid sample name in {kind}/: {entry}")
        names[stem] = Path(directory) / entry
    return names


def _load_legacy_manifests(root):
    """Validate identity and authoring pairs without Node or generated JavaScript."""
    root = Path(root)
    authored = (root / "src").exists() or (root / "src").is_symlink()
    directory, suffix = ("src", ".ts") if authored else ("scripts", ".js")
    scripts = _list_dir(root / directory, suffix, directory)
    manifests = _list_dir(root / "manifests", ".json", "manifests")
    if scripts.keys() != manifests.keys():
        missing = sorted(set(scripts) ^ set(manifests))
        raise ToolError(f"every sample needs both {directory}/NAME{suffix} and manifests/NAME.json; unpaired: " + ", ".join(missing))
    if not scripts:
        raise ToolError("no samples found")
    manifests_out, ids = [], {}
    for name in sorted(scripts):
        manifest = load_json(manifests[name], f"manifests/{name}.json")
        validate_manifest(manifest, f"manifests/{name}.json")
        authored_bytes = read_regular(scripts[name], MAX_SOURCE_BYTES)
        try:
            text = authored_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise ToolError(f"{directory}/{name}{suffix}: not valid UTF-8")
        if "\x00" in text:
            raise ToolError(f"{directory}/{name}{suffix}: contains NUL")
        identifier = manifest["id"].upper()
        if identifier in ids:
            raise ToolError(f"duplicate plugin id {identifier} in {name} and {ids[identifier]}")
        ids[identifier] = name
        manifests_out.append((name, manifest))
    return manifests_out


def load_manifests(root):
    """Validated authored identities and metadata; routed plugins need no generated artifacts."""
    from route_sources import discover
    root = Path(root)
    legacy = _load_legacy_manifests(root) if any((root / p).exists() for p in ('src', 'scripts', 'manifests')) else []
    routed = discover(root)
    result = legacy + [(name, item['metadata']) for name, item in routed.items()]
    names, ids = set(), set()
    for name, manifest in result:
        identifier = manifest['id'].upper()
        if name in names or identifier in ids:
            raise ToolError(f'duplicate plugin basename or id: {name}')
        names.add(name); ids.add(identifier)
    if not result:
        raise ToolError('no samples found')
    return sorted(result)


def _install_generated(root, scripts, manifests):
    """Install two dedicated generated directories, restoring both after an installation failure."""
    build = root / 'build'
    if build.is_symlink():
        raise ToolError('build must not be a symlink')
    build.mkdir(exist_ok=True)
    stamp = uuid.uuid4().hex
    staged, backups, installed = {}, {}, []
    try:
        for kind, values in (('scripts', scripts), ('manifests', manifests)):
            target = build / kind
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                raise ToolError(f'generated {kind} must be a real directory')
            stage = build / f'.{kind}.{stamp}'
            stage.mkdir()
            staged[target] = stage
            for relative, data in values.items():
                path = stage / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        for target, stage in staged.items():
            if target.exists():
                backup = build / f'.{target.name}.backup.{stamp}'
                os.replace(target, backup)
                backups[target] = backup
            os.replace(stage, target)
            installed.append(target)
    except BaseException:
        for target in reversed(installed):
            shutil.rmtree(target)
        for target, backup in backups.items():
            os.replace(backup, target)
        raise
    finally:
        for stage in staged.values():
            if stage.exists():
                shutil.rmtree(stage)
        for backup in backups.values():
            if backup.exists():
                shutil.rmtree(backup)


def load_samples(root):
    """Compile routed TS into manifest+files, preserving legacy single-script package bytes."""
    root = Path(root)
    authored = load_manifests(root)
    typed = (root / 'src').exists()
    routed = any(m['schemaVersion'] == 2 for _, m in authored)
    emitted = {}
    if typed or routed:
        result = subprocess.run(['bun', str(root / 'tools/compile.mjs'), str(root)], capture_output=True, text=True,
                                env=dict(os.environ, INTERCEPTOR_PYTHON=sys.executable))
        if result.returncode:
            raise ToolError('TypeScript compilation failed; run bun install --frozen-lockfile --ignore-scripts first if dependencies are missing:\n' + result.stderr)
        emitted = parse_json_object(result.stdout.encode('utf-8'), 'compiler output')
        expected = {name for name, m in authored if typed or m['schemaVersion'] == 2}
        if set(emitted) != expected:
            raise ToolError('compiler outputs do not match authored plugins')
    samples, scripts, manifests = [], {}, {}
    for name, metadata in authored:
        if metadata['schemaVersion'] == 2:
            package = emitted[name]
            require_exact_keys(package, ('manifest', 'sourceFiles'), name + ' compiler output')
            manifest, source = package['manifest'], package['sourceFiles']
            validate_manifest(manifest, name + ' generated manifest')
            if {k: v for k, v in manifest.items() if k != 'matches'} != metadata:
                raise ToolError(f'{name}: generated metadata differs from plugin.json')
            validate_source_files(manifest, source, name)
            for key, text in source.items():
                scripts[f'{name}/{key}'] = text.encode('utf-8')
        else:
            manifest = metadata
            raw = emitted[name].encode('utf-8') if typed else read_regular(root / 'scripts' / (name + '.js'), MAX_SOURCE_BYTES)
            source = raw.decode('utf-8')
            if len(raw) > MAX_SOURCE_BYTES or '\x00' in source:
                raise ToolError(f'{name}: invalid or oversized source')
            if typed:
                scripts[name + '.js'] = raw
        manifests[name + '.json'] = dump_json(manifest)
        samples.append((name, manifest, source))
    if typed or routed:
        _install_generated(root, scripts, manifests)
    return samples


def package_bytes(manifest, source):
    if manifest['schemaVersion'] == 2:
        validate_source_files(manifest, source, 'package')
        package = {'manifest': manifest, 'sourceFiles': source}
    else:
        package = {'manifest': manifest, 'source': source}
    data = json.dumps(package, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    if len(data) > MAX_PACKAGE_BYTES:
        raise ToolError('package exceeds the 256 KiB limit')
    return data


def new_uuid(taken):
    while True:
        candidate = str(uuid.uuid4()).upper()
        if candidate not in taken:
            return candidate


# ---------------------------------------------------------------- git origin

_OFFICIAL_ORIGIN = re.compile(r"github\.com[:/]+{owner}/{name}(?:\.git)?/*$", re.IGNORECASE)


def origin_is_official(root):
    """True when any remote of a Git checkout rooted exactly at ROOT points at the official repository.

    Remotes are read through Git so insteadOf rewrites and push URLs are honoured. If a .git entry exists but
    cannot be inspected, fail closed.
    """
    root = Path(root).resolve()
    if not os.path.lexists(root / ".git"):
        return False
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "0", "GIT_TERMINAL_PROMPT": "0"})

    def git(*args):
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env, timeout=30)
        if proc.returncode != 0:
            raise ToolError("cannot inspect Git remotes: " + (proc.stderr.strip() or "git failed"))
        return proc.stdout.splitlines()

    try:
        top = git("rev-parse", "--show-toplevel")
        if not top or Path(top[0]).resolve() != root:
            return False
        owner, name = (re.escape(part) for part in OFFICIAL_REPOSITORY.split("/"))
        pattern = re.compile(rf"github\.com[:/]+{owner}/{name}(?:\.git)?/*$", re.IGNORECASE)
        for remote in git("remote"):
            urls = git("remote", "get-url", "--all", remote) + git("remote", "get-url", "--push", "--all", remote)
            if any(pattern.search(url.strip()) for url in urls):
                return True
    except (OSError, subprocess.SubprocessError) as error:
        raise ToolError(f"cannot inspect Git remotes: {error}")
    return False


# ---------------------------------------------------------------- atomic writes

def write_all_or_nothing(files):
    """files: {Path: bytes}. Stage every file, then replace; roll back on any failure."""
    staged, originals, replaced = {}, {}, []
    try:
        for path, data in files.items():
            originals[path] = read_regular(path)
            temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
            staged[path] = temp
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        for path, temp in staged.items():
            os.replace(temp, path)
            replaced.append(path)
    except BaseException:
        for path in replaced:
            try:
                path.write_bytes(originals[path])
            except OSError:
                pass
        raise
    finally:
        for temp in staged.values():
            try:
                os.unlink(temp)
            except FileNotFoundError:
                pass
