
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from src.config import settings
from src.pipeline import parse_date, run_pipeline

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self): self._handle()
    def do_POST(self): self._handle()

    def _handle(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {"status": "ok", "service": "madrid-openmeteo-etl"})
            return
        if parsed.path == "/run":
            query = parse_qs(parsed.query)
            try:
                target_day = parse_date(query.get("date", [None])[0])
            except ValueError:
                self._send_json(400, {"status": "error", "message": "Invalid date. Use YYYY-MM-DD."})
                return
            manifest = run_pipeline(target_day)
            self._send_json(200 if manifest.get("status") == "success" else 500, manifest)
            return
        self._send_json(404, {"status": "error", "message": "Not found"})

    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))

def main():
    server = HTTPServer(("0.0.0.0", settings.etl_port), Handler)
    print(f"ETL service listening on port {settings.etl_port}")
    server.serve_forever()

if __name__ == "__main__":
    main()
