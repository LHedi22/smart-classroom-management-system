#!/usr/bin/env python3
"""
demo_launcher.py — Host-side launcher for live demo face recognition.

Runs on the HOST (not in Docker). Exposes a tiny HTTP API on port 8001
so the dashboard button can start/stop laptop_recognition.py.

Usage:
    python demo_launcher.py

Endpoints:
    GET  /status  — {"running": bool, "pid": int|null}
    POST /start   — spawn laptop_recognition.py, return status
    POST /stop    — terminate it, return status
"""

import json
import logging
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PORT = 8001
SCRIPT = Path(__file__).parent / "laptop_recognition.py"

_proc: subprocess.Popen | None = None


def _running() -> bool:
    return _proc is not None and _proc.poll() is None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # silence default request logs
        pass

    def _respond(self, data: dict, code: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._respond({})

    def do_GET(self):
        if self.path == "/status":
            self._respond({"running": _running(), "pid": _proc.pid if _running() else None})
        else:
            self._respond({"error": "not found"}, 404)

    def do_POST(self):
        global _proc
        if self.path == "/start":
            if _running():
                self._respond({"running": True, "pid": _proc.pid, "message": "Already running"})
                return
            if not SCRIPT.exists():
                self._respond({"error": f"Script not found: {SCRIPT}"}, 503)
                return
            _proc = subprocess.Popen(
                [sys.executable, str(SCRIPT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log.info("Started laptop_recognition.py (pid=%d)", _proc.pid)
            self._respond({"running": True, "pid": _proc.pid})

        elif self.path == "/stop":
            if not _running():
                self._respond({"running": False, "message": "Not running"})
                return
            pid = _proc.pid
            _proc.terminate()
            try:
                _proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _proc.kill()
            log.info("Stopped laptop_recognition.py (pid=%d)", pid)
            self._respond({"running": False})

        else:
            self._respond({"error": "not found"}, 404)


if __name__ == "__main__":
    log.info("Demo launcher running on http://localhost:%d", PORT)
    log.info("Script target: %s", SCRIPT)
    HTTPServer(("", PORT), Handler).serve_forever()
