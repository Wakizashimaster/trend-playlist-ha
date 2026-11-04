"""Durable, reversible exclusions for tracks manually removed in TIDAL.

This store is intentionally separate from the permanent artist/song blocklist.
Callers must verify playlist identity, obtain complete stable live reads, and
check the publish recovery journal *before* calling reconcile_and_save.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from manual_reconciliation import reconcile, next_exclusions

SCHEMA = 1

def load(path, playlist_id):
    path = Path(path)
    if not path.exists():
        return {"schema": SCHEMA, "playlist_id": playlist_id, "excluded_ids": [], "events": []}
    record = json.loads(path.read_text(encoding="utf-8"))
    if (record.get("schema") != SCHEMA or record.get("playlist_id") != playlist_id
            or not isinstance(record.get("excluded_ids"), list)
            or not isinstance(record.get("events"), list)
            or any(not str(t).isdigit() for t in record["excluded_ids"])):
        raise ValueError("Invalid manual-exclusions store; refusing reconciliation")
    if len(record["excluded_ids"]) != len(set(record["excluded_ids"])):
        raise ValueError("Duplicate manual exclusions")
    return record

def atomic_write(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".manual-exclusions-", suffix=".tmp",
                                     delete=False) as stream:
        tmp = Path(stream.name)
        try:
            json.dump(record, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

def plan(previous_ids, live_ids, store, *, min_tracks=20, max_edits=10):
    """Compute the next record without modifying any files."""
    result = reconcile(previous_ids, live_ids, store["excluded_ids"],
                       min_tracks=min_tracks, max_edits=max_edits)
    excluded = next_exclusions(store["excluded_ids"], result)
    now = datetime.now(timezone.utc).isoformat()
    events = list(store["events"])
    events.extend({"at": now, "tidal_id": tid, "action": "excluded", "source": "tidal_manual_removal"}
                  for tid in result.removed_ids)
    events.extend({"at": now, "tidal_id": tid, "action": "restored", "source": "tidal_manual_readd"}
                  for tid in result.restored_ids)
    updated = {**store, "excluded_ids": sorted(excluded), "events": events}
    return result, updated
