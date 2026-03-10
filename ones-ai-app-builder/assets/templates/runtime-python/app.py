import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = {
            "ok": True,
            "runtime": "python311",
            "appId": os.environ.get("APP_ID", "unknown"),
            "dataDir": os.environ.get("APP_DATA_DIR", "/data"),
            "releaseVersion": os.environ.get("RELEASE_VERSION", "dev"),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()
