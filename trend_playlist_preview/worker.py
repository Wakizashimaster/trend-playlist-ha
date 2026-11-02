"""HA OS add-on: token-protected read-only preview and Monday schedule."""
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("/opt/trend")
DATA = Path("/config")
REPORT = DATA / "ha_preview_status.json"
os.environ["TREND_PLAYLIST_DATA"] = str(DATA)
TOKEN = json.loads(Path("/data/options.json").read_text()).get("api_token", "")
if len(TOKEN) < 24:
    sys.exit("Configure a random API token of at least 24 characters in add-on options")
lock = threading.Lock()
state = {"running": False, "last_run": None, "ok": None, "message": "Not run yet"}
if REPORT.exists():
    try:
        state.update(json.loads(REPORT.read_text()))
    except (OSError, ValueError):
        pass
state["running"] = False

def run_preview():
    if not lock.acquire(blocking=False):
        return False
    state["running"] = True
    try:
        result = subprocess.run([sys.executable, str(ROOT / "auto_refresh.py"), "--preview"],
            cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True, timeout=7200)
        state.update(last_run=datetime.now(ZoneInfo("Europe/London")).isoformat(),
            ok=result.returncode == 0, message=(result.stdout + "\n" + result.stderr)[-5000:])
        REPORT.write_text(json.dumps({k:v for k,v in state.items() if k != "running"}, indent=2))
    except Exception as exc:
        state.update(ok=False, message=str(exc), last_run=datetime.now(ZoneInfo("Europe/London")).isoformat())
    finally:
        state["running"] = False
        lock.release()
    return True

def scheduler():
    last_day = None
    while True:
        now = datetime.now(ZoneInfo("Europe/London"))
        if now.weekday() == 0 and now.hour == 8 and now.minute < 5 and last_day != now.date():
            last_day = now.date()
            threading.Thread(target=run_preview, daemon=True).start()
        time.sleep(30)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def respond(self, code, data):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def authorized(self):
        import hmac
        return hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + TOKEN)
    def do_GET(self):
        if not self.authorized():
            return self.respond(401, {"error": "unauthorized"})
        if self.path == "/status":
            return self.respond(200, dict(state))
        return self.respond(404, {"error": "not found"})
    def do_POST(self):
        if not self.authorized():
            return self.respond(401, {"error": "unauthorized"})
        if self.path != "/preview":
            return self.respond(404, {"error": "not found"})
        if lock.locked():
            return self.respond(409, {"error": "preview already running"})
        threading.Thread(target=run_preview, daemon=True).start()
        return self.respond(202, {"started": True})

threading.Thread(target=scheduler, daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()
