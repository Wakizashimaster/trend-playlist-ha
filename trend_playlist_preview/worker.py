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

def build_review():
    """Read-only, named changes from the latest successful preview."""
    import csv
    def rows(filename):
        path = DATA / filename
        if not path.exists():
            return []
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    if state.get("running") or state.get("ok") is not True:
        return {"ready": False, "reason": "No completed successful preview"}
    baseline = json.loads((DATA / "auto_refresh_state.json").read_text())
    original = [str(x) for x in baseline["track_ids"]]
    matches = rows("match_report.csv")
    if not matches or any(row.get("status") != "matched" for row in matches):
        return {"ready": False, "reason": "Matching report incomplete"}
    proposed = [row["tidal_id"] for row in matches]
    if len(proposed) != len(set(proposed)):
        return {"ready": False, "reason": "Duplicate TIDAL IDs"}
    old, new = set(original), set(proposed)
    named = lambda row: {"artist": row["artist"], "title": row["title"], "tidal_id": row["tidal_id"]}
    return {"ready": True, "last_run": state["last_run"],
            "playlist_name": "Down with the Kids", "target": 50,
            "proposed_count": len(proposed),
            "additions": [named(r) for r in matches if r["tidal_id"] not in old],
            "removals": [{"tidal_id": x} for x in original if x not in new],
            "unchanged": len(old & new),
            "review_candidates": [{"artist": r["artist"], "title": r["title"],
                                   "release_status": r.get("release_status", "")}
                                  for r in rows("review.csv")],
            "publish_enabled": False}

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
        if self.path == "/review":
            try:
                return self.respond(200, build_review())
            except (OSError, ValueError, KeyError) as exc:
                return self.respond(503, {"ready": False, "reason": str(exc)})
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
