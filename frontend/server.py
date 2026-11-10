#!/usr/bin/env python3
"""Basic frontend server for the AnySearch skill."""

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CLI_PATH = os.path.join(PROJECT_ROOT, "scripts", "anysearch_cli.py")
FRONTEND_ROOT = os.path.dirname(os.path.abspath(__file__))


class FrontendServer(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        return

    def serve_static_file(self, relative_path: str, content_type: str):
        file_path = os.path.join(FRONTEND_ROOT, relative_path.lstrip("/"))
        if not os.path.isfile(file_path):
            self.send_error(404)
            return

        with open(file_path, "rb") as handle:
            content = handle.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        request_path = urlparse(self.path).path

        if request_path in ("/", "/index.html"):
            self.serve_static_file("index.html", "text/html; charset=utf-8")
            return

        if request_path == "/styles.css":
            self.serve_static_file("styles.css", "text/css; charset=utf-8")
            return

        if request_path == "/app.js":
            self.serve_static_file("app.js", "application/javascript; charset=utf-8")
            return

        self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/search":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_data = self.rfile.read(length)
            payload = json.loads(raw_data.decode("utf-8")) if raw_data else {}
        except (ValueError, UnicodeDecodeError):
            self._send_json(400, {"error": "Request body must be valid JSON."})
            return

        queries = payload.get("queries")
        if queries is None:
            single_topic = str(payload.get("topic") or payload.get("query") or "").strip()
            queries = [single_topic] if single_topic else []
        elif isinstance(queries, str):
            cleaned = queries.strip()
            if cleaned.startswith("["):
                try:
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, list):
                        queries = [str(item.get("query") if isinstance(item, dict) else item).strip() for item in parsed if (item.get("query") if isinstance(item, dict) else str(item).strip())]
                    else:
                        queries = [str(parsed).strip()]
                except (TypeError, ValueError):
                    queries = [cleaned]
            else:
                queries = [line.strip() for line in cleaned.splitlines() if line.strip()]
        elif isinstance(queries, list):
            normalized = []
            for item in queries:
                if isinstance(item, dict):
                    q = str(item.get("query") or item.get("topic") or "").strip()
                else:
                    q = str(item).strip()
                if q:
                    normalized.append(q)
            queries = normalized

        if not queries:
            self._send_json(400, {"error": "Please provide at least one query to search."})
            return

        try:
            if len(queries) == 1:
                result = subprocess.run(
                    [sys.executable, CLI_PATH, "search", queries[0], "--max_results", "5"],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
            else:
                batch_payload = json.dumps([{"query": q} for q in queries], ensure_ascii=False)
                result = subprocess.run(
                    [sys.executable, CLI_PATH, "batch_search", "--queries", batch_payload],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
        except subprocess.TimeoutExpired:
            self._send_json(504, {"error": "The search request timed out. Please try again."})
            return

        if result.returncode != 0:
            error_text = (result.stderr or result.stdout or "Unknown error").strip()
            self._send_json(500, {"error": error_text[:500]})
            return

        self._send_json(200, {
            "queries": queries,
            "results": self._parse_search_output(result.stdout),
            "raw": result.stdout.strip(),
        })

    def _parse_search_output(self, output: str):
        if not output:
            return []

        lines = [line.rstrip() for line in output.splitlines() if line.strip()]
        results = []
        current = {}

        for line in lines:
            if line.startswith("### "):
                if current and (current.get("title") or current.get("url") or current.get("content")):
                    results.append(current)
                current = {"title": line.replace("### ", "", 1).strip()}
                continue

            if line.startswith("- **URL**:"):
                current["url"] = line.replace("- **URL**:", "", 1).strip()
                continue

            if line.startswith("- "):
                snippet = line[2:].strip()
                if not snippet:
                    continue
                if current.get("content"):
                    current["content"] = current["content"] + " " + snippet
                else:
                    current["content"] = snippet

        if current and (current.get("title") or current.get("url") or current.get("content")):
            results.append(current)

        return results

    def _send_json(self, status_code: int, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), FrontendServer)
    print(f"AnySearch frontend running at http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
