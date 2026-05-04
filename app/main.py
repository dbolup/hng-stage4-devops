import os
import time
import random
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# ── Config from environment ──────────────────────────
MODE = os.environ.get("MODE", "stable")
VERSION = os.environ.get("APP_VERSION", "1.0.0")
PORT = int(os.environ.get("APP_PORT", 3000))
START_TIME = time.time()

# ── Chaos state ──────────────────────────────────────
chaos_state = {
    "mode": None,       # "slow", "error", "recover", None
    "duration": 0,      # for slow mode
    "rate": 0.0,        # for error mode
    "timer": None       # for auto-recover
}
chaos_lock = threading.Lock()


def apply_chaos_headers(handler):
    """Add X-Mode header if canary."""
    if MODE == "canary":
        handler.send_header("X-Mode", "canary")


def should_return_error():
    """Check if chaos error mode should fire."""
    with chaos_lock:
        if chaos_state["mode"] == "error":
            return random.random() < chaos_state["rate"]
    return False


def get_chaos_delay():
    """Return delay seconds if chaos slow mode active."""
    with chaos_lock:
        if chaos_state["mode"] == "slow":
            return chaos_state["duration"]
    return 0


class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Suppress default logs

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        apply_chaos_headers(self)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Chaos error check
        if should_return_error():
            self.send_json(500, {
                "error": "chaos error injection",
                "mode": MODE
            })
            return

        # Chaos slow check
        delay = get_chaos_delay()
        if delay > 0:
            time.sleep(delay)

        if self.path == "/":
            self.send_json(200, {
                "message": f"Welcome! Running in {MODE} mode",
                "mode": MODE,
                "version": VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        elif self.path == "/healthz":
            uptime = round(time.time() - START_TIME, 2)
            self.send_json(200, {
                "status": "ok",
                "mode": MODE,
                "version": VERSION,
                "uptime_seconds": uptime
            })

        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/chaos":
            # Only canary mode can use chaos
            if MODE != "canary":
                self.send_json(403, {
                    "error": "chaos endpoint only available in canary mode"
                })
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                data = json.loads(body)
            except Exception:
                self.send_json(400, {"error": "invalid JSON"})
                return

            with chaos_lock:
                mode = data.get("mode")

                if mode == "slow":
                    chaos_state["mode"] = "slow"
                    chaos_state["duration"] = int(data.get("duration", 2))
                    self.send_json(200, {
                        "chaos": "slow mode activated",
                        "duration": chaos_state["duration"]
                    })

                elif mode == "error":
                    chaos_state["mode"] = "error"
                    chaos_state["rate"] = float(data.get("rate", 0.5))
                    self.send_json(200, {
                        "chaos": "error mode activated",
                        "rate": chaos_state["rate"]
                    })

                elif mode == "recover":
                    chaos_state["mode"] = None
                    chaos_state["duration"] = 0
                    chaos_state["rate"] = 0.0
                    self.send_json(200, {"chaos": "recovered"})

                else:
                    self.send_json(400, {
                        "error": "unknown chaos mode",
                        "valid": ["slow", "error", "recover"]
                    })
        else:
            self.send_json(404, {"error": "not found"})


if __name__ == "__main__":
    print(f"Starting API in {MODE} mode on port {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
