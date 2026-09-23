"""Local HTTP fixture: python3 tests/http_fixture.py (then tests/test_http.R)."""

import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

CSV = b"id;value\n1;0\n"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if urlsplit(self.path).path != "/api-token-auth/":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        fields = parse_qs(self.rfile.read(length).decode("utf-8"))
        if fields.get("username") != ["demo"] or fields.get("password") != [
            "päss&word"
        ]:
            self.send_error(400)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"token":"fixture-secret"}')

    def do_GET(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/waste_collection/api/collection/analysis/":
            private = (
                parse_qs(parsed.query).get("scope", ["published"])[0] != "published"
            )
            if private and self.headers.get("Authorization") != "Token fixture-secret":
                self.send_error(401)
                return
            data = {
                "schema_version": "1.0",
                "count": 2,
                "next": base + ("/page2-private" if private else "/page2"),
                "results": [
                    {
                        "id": 1,
                        "nuts_or_lau_id": "00123",
                        "country": None,
                        "connection_rate_2024": 0,
                        "connection_rate_2024_unit": "%",
                    }
                ],
            }
        elif path in {"/page2", "/page2-private"}:
            if (
                path == "/page2-private"
                and self.headers.get("Authorization") != "Token fixture-secret"
            ):
                self.send_error(401)
                return
            data = {
                "schema_version": "1.0",
                "count": 2,
                "next": None,
                "results": [{"id": 2, "nuts_or_lau_id": "00456", "country": None}],
            }
        elif path == "/release/data/manifest.json":
            data = {
                "schema_version": "1.0",
                "release_id": "http-test",
                "files": [
                    {
                        "path": "data/raw/test.csv",
                        "sha256": hashlib.sha256(CSV).hexdigest(),
                    }
                ],
            }
        elif path == "/release/data/raw/test.csv":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(CSV)
            return
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 18875), Handler).serve_forever()
