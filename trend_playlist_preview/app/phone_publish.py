"""Explicitly approved, fail-closed in-place publisher. Never creates/deletes playlists."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import tidalapi
import auto_refresh as ar
import trend_playlist as tp

DATA = tp.DATA
JOURNAL = DATA / "phone_publish_journal.json"
PLAYLIST_ID = ar.PLAYLIST_ID

def atomic_json(path, value):
    import tempfile
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                     prefix=".publish-", suffix=".tmp", delete=False) as f:
        tmp = Path(f.name)
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def publish(plan_file):
    if (DATA / "manual_reconciliation_pending.json").exists():
        raise RuntimeError("Unresolved manual reconciliation; publishing blocked")
    plan = json.loads(Path(plan_file).read_text(encoding="utf-8"))
    original = [str(x) for x in plan["original_ids"]]
    proposed = [str(x) for x in plan["proposed_ids"]]
    if plan.get("playlist_id") != PLAYLIST_ID or not original or not proposed:
        raise RuntimeError("Invalid locked playlist identity or empty track sequence")
    if len(proposed) < 20 or len(proposed) > 50 or len(set(proposed)) != len(proposed):
        raise RuntimeError("Approved plan fails track-count/duplicate safeguards")
    if len(set(original) & set(proposed)) / len(set(original)) < ar.MIN_RETENTION:
        raise RuntimeError("Approved plan exceeds retention safety limit")
    if len(set(original) ^ set(proposed)) / max(len(original), len(proposed)) > ar.MAX_CHANGED_FRACTION:
        raise RuntimeError("Approved plan exceeds change safety limit")
    state = json.loads(ar.STATE.read_text(encoding="utf-8"))
    if state.get("playlist_id") not in (None, PLAYLIST_ID) or [str(x) for x in state["track_ids"]] != original:
        raise RuntimeError("Baseline changed after approval")
    if JOURNAL.exists():
        journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
        if journal.get("status") not in ("verified",):
            raise RuntimeError("Unresolved prior publishing attempt; inspect recovery before retry")
    session = tidalapi.Session()
    if not session.login_session_file(tp.SESSION_FILE):
        raise RuntimeError("TIDAL login failed")
    matches = [p for p in session.user.playlists() if str(p.id) == PLAYLIST_ID]
    if len(matches) != 1 or matches[0].name != "Down with the Kids":
        raise RuntimeError("Protected playlist missing or renamed")
    playlist = matches[0]
    if tp.read_playlist_ids(playlist) != original:
        raise RuntimeError("Live playlist changed; refusing to publish")
    if proposed == original:
        atomic_json(JOURNAL, {"status": "verified", "proposal_id": plan["proposal_id"],
                              "playlist_id": PLAYLIST_ID, "track_ids": proposed, "no_change": True})
        return
    # Durable intent journal before the first remote write. If process/network dies,
    # the next publish is blocked until supervised reconciliation.
    atomic_json(JOURNAL, {"status": "started", "proposal_id": plan["proposal_id"],
                          "playlist_id": PLAYLIST_ID, "original_ids": original,
                          "proposed_ids": proposed,
                          "started_at": datetime.now(timezone.utc).isoformat()})
    try:
        snapshot = tp.update_playlist_in_place(playlist, original, proposed)
        if tp.read_playlist_ids(playlist) != proposed:
            raise RuntimeError("Final live track verification failed")
        # The existing playlist object is never deleted or replaced.
        atomic_json(ar.STATE, {"playlist_id": PLAYLIST_ID, "playlist_name": "Down with the Kids",
                               "track_ids": proposed, "updated_at": datetime.now(timezone.utc).isoformat()})
        atomic_json(JOURNAL, {"status": "verified", "proposal_id": plan["proposal_id"],
                              "playlist_id": PLAYLIST_ID, "track_ids": proposed,
                              "snapshot": str(snapshot),
                              "completed_at": datetime.now(timezone.utc).isoformat()})
    except Exception as exc:
        atomic_json(JOURNAL, {"status": "needs_manual_recovery", "proposal_id": plan["proposal_id"],
                              "playlist_id": PLAYLIST_ID, "original_ids": original,
                              "proposed_ids": proposed, "error": str(exc)})
        raise

if __name__ == "__main__":
    publish(sys.argv[1])
