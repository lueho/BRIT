"""Local HTTP fixture: python3 tests/http_fixture.py (then tests/test_http.R)."""

import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

CSV = b"id;value\n1;0\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        path = urlsplit(self.path).path
        if path == "/waste_collection/api/collection/analysis/":
            data = {
                "schema_version": "1.0",
                "count": 2,
                "next": base + "/page2",
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
        elif path == "/page2":
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
