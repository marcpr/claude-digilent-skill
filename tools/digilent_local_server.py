#!/usr/bin/env python3
"""
Digilent Local Server

A lightweight HTTP server that exposes the Digilent WaveForms instrument
connected via USB to this machine over a local HTTP API.

Usage:
    python tools/digilent_local_server.py
    python tools/digilent_local_server.py --port 7272
    python tools/digilent_local_server.py --no-auto-open

See .claude/skills/digilent-local/SKILL.md for usage with Claude Code.
"""

import argparse
import atexit
import http.server
import json
import logging
import signal
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the repo root (parent of tools/) is on sys.path so `import digilent`
# resolves to the digilent/ package next to tools/.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import digilent.api as _api
from digilent.config import DigilentConfig

logging.basicConfig(
    level=logging.INFO,
    format="[digilent-local] %(message)s",
)
_log = logging.getLogger("digilent-local")

DEFAULT_PORT = 7272
DEFAULT_HOST = "127.0.0.1"


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        _log.debug(fmt, *args)

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path

        if path.startswith("/api/digilent"):
            _api.handle_get(self, path)
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path

        if path.startswith("/api/digilent"):
            _api.handle_post(self, path)
        else:
            self._send_json({"error": "not found"}, 404)


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------

def _print_banner(host: str, port: int) -> None:
    state = _api._manager.status_dict() if _api._manager else {}
    device_name = state.get("device_name") or "none"
    device_state = state.get("state", "absent")

    print(f"[digilent-local] Server listening on http://{host}:{port}", flush=True)
    if device_state == "idle":
        print(f"[digilent-local] Device: {device_name} (open)", flush=True)
    elif device_state == "absent":
        print(
            "[digilent-local] WARNING: No Digilent device detected. "
            "Connect the device and call POST /api/digilent/device/open",
            flush=True,
        )
    else:
        print(f"[digilent-local] Device state: {device_state}", flush=True)
    print("[digilent-local] Press Ctrl+C to stop", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Digilent local HTTP server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"TCP port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"Bind address (default: {DEFAULT_HOST})")
    parser.add_argument("--no-auto-open", action="store_true",
                        help="Do not open the device at startup")
    parser.add_argument("--allow-supplies", action="store_true",
                        help="Enable power supply endpoints (disabled by default)")
    parser.add_argument("--config", default=None,
                        help="Path to digilent config JSON (optional)")
    args = parser.parse_args()

    # Build config
    if args.config:
        from digilent.config import load_config
        cfg = load_config(args.config)
    else:
        cfg = DigilentConfig(
            auto_open=not args.no_auto_open,
            allow_supplies=args.allow_supplies,
        )

    # Initialise services
    _api.init_with_config(cfg)

    # Register shutdown
    def _shutdown(*_):
        _log.info("Shutting down ...")
        _api.shutdown()
        sys.exit(0)

    atexit.register(_api.shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Start HTTP server
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    httpd = http.server.ThreadingHTTPServer((args.host, args.port), Handler)

    _print_banner(args.host, args.port)

    httpd.serve_forever()


if __name__ == "__main__":
    main()
