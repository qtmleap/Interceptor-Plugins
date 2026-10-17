#!/usr/bin/env python3
"""Download prior metadata. Exit 3 means HTTP404; all other failures are fatal."""
import argparse
import math
import os
from pathlib import Path
import signal
import ssl
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 768 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download(url, output, timeout):
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != "https" or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment):
        raise ValueError("a credential-free HTTPS feed URL is required")
    if not math.isfinite(timeout) or not 0 < timeout <= 15:
        raise ValueError("timeout must be greater than zero and at most 15 seconds")

    def expired(signum, frame):
        raise TimeoutError("previous-feed deadline exceeded")

    previous_handler = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError(f"unexpected HTTP status {response.status}")
            declared = response.headers.get("Content-Length")
            if declared is not None and (not declared.isdecimal() or int(declared) > MAX_BYTES):
                raise ValueError("invalid or oversized previous-feed Content-Length")
            data = bytearray()
            while True:
                chunk = response.read(min(65536, MAX_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError("previous feed exceeds 768 KiB")
        if not data:
            raise ValueError("previous feed is empty")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".previous-", delete=False) as file:
                temporary = Path(file.name)
                file.write(data)
            os.replace(temporary, output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    try:
        download(args.url, args.output, args.timeout)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            print("HTTP404: first publication", file=sys.stderr)
            return 3
        print(f"previous-feed fetch failed: HTTP {error.code}; redirects are refused", file=sys.stderr)
        return 1
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"previous-feed fetch failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
