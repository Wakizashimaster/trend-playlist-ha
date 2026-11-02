"""HA OS add-on: token-protected read-only preview and Monday schedule."""
import json
import hashlib
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
    (DATA / "phone_candidate_pool.csv").unlink(missing_ok=True)
    (DATA / "phone_baseline_tracks.json").unlink(missing_ok=True)
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
    try:
        metadata = json.loads((DATA / "phone_baseline_tracks.json").read_text(encoding="utf-8"))
        if [str(x) for x in metadata["track_ids"]] != original:
            raise ValueError("baseline metadata mismatch")
        named_original = {str(r["tidal_id"]): {"tidal_id": str(r["tidal_id"]),
                          "artist": r["artist"], "title": r["title"]} for r in metadata["tracks"]}
    except (OSError, ValueError, KeyError, TypeError):
        named_original = {}
    removal = lambda tid: named_original.get(tid, {"tidal_id": tid})

    pool = rows("phone_candidate_pool.csv")
    pool_ids = [r["tidal_id"] for r in pool if r.get("tidal_id")]
    if not pool or pool_ids[:len(proposed)] != proposed:
        return {"ready": False, "reason": "Reserve pool missing or mismatched; rerun preview"}

    named = lambda row: {"artist": row["artist"], "title": row["title"], "tidal_id": row["tidal_id"]}
    proposal_id = hashlib.sha256(json.dumps({"run": state["last_run"], "old": original, "new": proposed}, sort_keys=True).encode()).hexdigest()[:20]
    try:
        saved = json.loads((DATA / "phone_review.json").read_text())
    except (OSError, ValueError):
        saved = {}
    decisions = saved.get("decisions", {}) if saved.get("proposal_id") == proposal_id else {}
    excluded = {tid for tid, action in decisions.items() if action in ("exclude", "block")}
    retained = {tid for tid, action in decisions.items() if action == "retain" and tid in old and tid not in new}
    revised = [removal(tid) for tid in original if tid in retained]
    seen = set(retained)
    for row in pool:
        tid = row["tidal_id"]
        if tid not in excluded and tid not in seen:
            revised.append(row)
            seen.add(tid)
        if len(revised) == 50:
            break
    revised_ids = {r["tidal_id"] for r in revised}
    zeitgeist = [named(r) for r in pool if decisions.get(r["tidal_id"]) == "zeitgeist"]
    # Zeitgeist intent is independent of the main playlist's revised inclusion.

    revised_track_ids = [r["tidal_id"] for r in revised]
    plan_hash = hashlib.sha256(json.dumps(revised_track_ids).encode()).hexdigest()[:20]
    approval = saved.get("approval", {}) if saved.get("proposal_id") == proposal_id else {}
    approved = approval.get("plan_hash") == plan_hash
    return {"ready": True, "proposal_id": proposal_id, "decisions": decisions,
            "plan_hash": plan_hash, "approval_recorded": approved,
            "revised_track_ids": revised_track_ids,
            "zeitgeist_pending": zeitgeist,
            "approval_mode": approval.get("mode") if approved else None,
            "revised_count": len(revised),
            "revised_additions": [named(r) for r in revised if r["tidal_id"] not in old],
            "revised_removals": [removal(x) for x in original if x not in revised_ids],
            "replacement_count": sum(r["tidal_id"] not in proposed for r in revised),
            "last_run": state["last_run"],
            "playlist_name": "Down with the Kids", "target": 50,
            "proposed_count": len(proposed),
            "additions": [named(r) for r in matches if r["tidal_id"] not in old],
            "removals": [removal(x) for x in original if x not in new],
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
        if self.path == "/decision":
            if lock.locked():
                return self.respond(409, {"error": "preview running"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 2048:
                    return self.respond(400, {"error": "invalid request size"})
                payload = json.loads(self.rfile.read(size))
                review = build_review()
                if not review.get("ready") or payload.get("proposal_id") != review["proposal_id"]:
                    return self.respond(409, {"error": "stale proposal"})
                tid = str(payload.get("tidal_id", ""))
                action = payload.get("action")
                additions = {r["tidal_id"] for r in review["additions"]}
                removals = {r["tidal_id"] for r in review["removals"]}
                if not ((tid in additions and action in ("keep", "exclude", "zeitgeist", "block")) or
                        (tid in removals and action in ("retain", "remove"))):
                    return self.respond(400, {"error": "invalid selection"})
                decisions = dict(review["decisions"])
                if action in ("keep", "remove"):
                    decisions.pop(tid, None)
                else:
                    decisions[tid] = action
                path = DATA / "phone_review.json"
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps({"proposal_id": review["proposal_id"], "decisions": decisions}, indent=2))
                os.replace(tmp, path)
                return self.respond(200, {"saved": True, "publish_enabled": False})
            except (ValueError, KeyError, OSError, TypeError) as exc:
                return self.respond(400, {"error": str(exc)})
        if self.path == "/approve":
            if lock.locked():
                return self.respond(409, {"error": "preview running"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 2048:
                    return self.respond(400, {"error": "invalid request"})
                payload = json.loads(self.rfile.read(size))
                review = build_review()
                if (not review.get("ready") or payload.get("proposal_id") != review["proposal_id"]
                        or payload.get("plan_hash") != review["plan_hash"]):
                    return self.respond(409, {"error": "proposal changed; review again"})
                mode = payload.get("mode")
                if mode not in ("custom", "everything"):
                    return self.respond(400, {"error": "invalid mode"})
                if mode == "everything" and review["decisions"]:
                    return self.respond(409, {"error": "Clear individual choices before Approve Everything"})
                path = DATA / "phone_review.json"
                record = {"proposal_id": review["proposal_id"], "decisions": review["decisions"],
                          "approval": {"plan_hash": review["plan_hash"], "mode": mode,
                                       "track_ids": review["revised_track_ids"],
                                       "recorded_at": datetime.now(ZoneInfo("Europe/London")).isoformat(),
                                       "publish_enabled": False}}
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(record, indent=2))
                os.replace(tmp, path)
                return self.respond(200, {"approval_recorded": True, "publish_enabled": False})
            except (ValueError, KeyError, OSError, TypeError) as exc:
                return self.respond(400, {"error": str(exc)})
        if self.path != "/preview":
            return self.respond(404, {"error": "not found"})
        if lock.locked():
            return self.respond(409, {"error": "preview already running"})
        threading.Thread(target=run_preview, daemon=True).start()
        return self.respond(202, {"started": True})

threading.Thread(target=scheduler, daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()
