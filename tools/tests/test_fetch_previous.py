"""Exercise real HTTPS requests, status handling, redirects and bounded output."""
import http.server
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest


class PreviousFeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="interceptor-fetch-tests-")
        cls.directory = Path(cls.temp.name)
        config = cls.directory / "certificate.ini"
        config.write_text("[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=localhost\n[ext]\nsubjectAltName=DNS:localhost\nbasicConstraints=critical,CA:TRUE\n")
        cls.cert = cls.directory / "cert.pem"
        subprocess.run(["openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048", "-days", "1", "-config", str(config), "-keyout", str(cls.directory / "key.pem"), "-out", str(cls.cert)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                cls.requests.append((self.path, self.headers.get("Authorization"), self.headers.get("Cookie")))
                if self.path == "/missing":
                    self.send_response(404)
                    self.end_headers()
                    return
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/target")
                    self.end_headers()
                    return
                if self.path == "/error":
                    self.send_response(503)
                    self.end_headers()
                    return
                self.send_response(200)
                if self.path == "/large":
                    self.send_header("Content-Length", "786433")
                    self.end_headers()
                    return
                self.end_headers()
                try:
                    if self.path == "/slow":
                        time.sleep(0.6)
                    self.wfile.write(b'{"previous":"exact bytes"}\n')
                except (OSError, ssl.SSLError):
                    pass

        cls.server = http.server.ThreadingHTTPServer(("localhost", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cls.cert), str(cls.directory / "key.pem"))
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temp.cleanup()

    def call(self, path, timeout="2"):
        output = self.directory / "previous.json"
        output.write_bytes(b"preserved")
        env = dict(os.environ, SSL_CERT_FILE=str(self.cert))
        script = Path(__file__).resolve().parents[1] / "fetch_previous.py"
        result = subprocess.run([sys.executable, str(script), "--url", f"https://localhost:{self.server.server_port}{path}", "--output", str(output), "--timeout", timeout], capture_output=True, text=True, env=env, timeout=5)
        return result, output

    def test_success_saves_exact_bytes_without_credentials(self):
        result, output = self.call("/ok")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes(), b'{"previous":"exact bytes"}\n')
        self.assertEqual(self.requests[-1], ("/ok", None, None))

    def test_only_404_is_first_publication(self):
        result, output = self.call("/missing")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(output.read_bytes(), b"preserved")
        result, _ = self.call("/error")
        self.assertEqual(result.returncode, 1)

    def test_redirect_is_not_followed(self):
        self.requests.clear()
        result, output = self.call("/redirect")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(output.read_bytes(), b"preserved")
        self.assertEqual([r[0] for r in self.requests], ["/redirect"])

    def test_oversize_does_not_replace_existing_file(self):
        result, output = self.call("/large")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(output.read_bytes(), b"preserved")

    def test_timeout_is_bounded(self):
        start = time.monotonic()
        result, output = self.call("/slow", "0.2")
        self.assertEqual(result.returncode, 1)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(output.read_bytes(), b"preserved")


if __name__ == "__main__":
    unittest.main()
