"""Fail-closed unattended refresh. Run only after manually verifying a real push.

Usage: python auto_refresh.py [--preview]
Schedule weekly with Windows Task Scheduler, not a public web server.
"""
import csv
import json
import os
import subprocess
import tempfile
import sys
from datetime import datetime, timezone
from pathlib import Path

import trend_playlist as tp

MIN_TRACKS = 20
MIN_MARKET_ROWS = 25
MIN_RETENTION = 0.60
MAX_CHANGED_FRACTION = 0.50
STATE = tp.DATA / "auto_refresh_state.json"
PLAYLIST_ID = "ac2a24f5-a386-40cb-a637-ad9f89f32622"


def run(*args):
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("trend_playlist.py")), *args],
                            stdin=subprocess.DEVNULL, check=False)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed with exit code {result.returncode}")


def verify_plan(previous_ids, new_ids, market_rows):
    if market_rows < MIN_MARKET_ROWS:
        raise RuntimeError(f"Only {market_rows} independently chart-sourced review rows")
    if len(new_ids) < MIN_TRACKS or len(set(new_ids)) != len(new_ids):
        raise RuntimeError("Too few or duplicate proposed TIDAL tracks")
    if not previous_ids:
        raise RuntimeError("No trusted prior successful automated baseline; bootstrap manually")
    old, new = set(previous_ids), set(new_ids)
    if len(old & new) / len(old) < MIN_RETENTION:
        raise RuntimeError("Proposed update removes too many existing tracks")
    if len(old ^ new) / max(len(old), len(new)) > MAX_CHANGED_FRACTION:
        raise RuntimeError("Proposed update changes too many tracks")
    return {"added": sorted(new - old), "removed": sorted(old - new)}


def save_state(data):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=STATE.parent,
                                     prefix=".refresh-", suffix=".tmp", delete=False) as handle:
        tmp = Path(handle.name)
        json.dump(data, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, STATE)


def verify_source_health():
    """Check raw independent feeds before sweep changes review.csv."""
    from types import SimpleNamespace
    args = SimpleNamespace(official_chart=True, spotify_mirror=True,
                           country="gb", apple_depth=100, tokchart=False)
    sources = tp.gather_sources(args)
    counts = {name: len(sources.get(name, [])) for name in ("chart", "apple", "spotify")}
    now = datetime.now(timezone.utc).timestamp()
    for name, cache_name, max_hours in (
        ("chart", "official_chart", 168),
        ("spotify", "spotify_uk_kworb", 24),
    ):
        cache_path = tp.DATA / "source_cache" / f"{cache_name}.json"
        try:
            metadata = json.loads(cache_path.read_text(encoding="utf-8"))
            age = now - float(metadata["fetched_at"])
            if not 0 <= age <= max_hours * 3600:
                counts[name] = 0
                print(f"warning: {name} cache exceeds {max_hours}h freshness limit", flush=True)
        except (OSError, ValueError, KeyError, TypeError):
            counts[name] = 0
            print(f"warning: {name} lacks a verifiable fresh cache", flush=True)
    # Manual chart CSV overrides are not independently dated: never count them.
    if tp.read_pairs(tp.INPUTS / "uk_chart.csv"):
        counts["chart"] = 0
        print("warning: manual chart override excluded from unattended health checks", flush=True)
    if sum(count >= 50 for count in counts.values()) < 2:
        raise RuntimeError(f"Fewer than two fresh chart sources with 50 tracks: {counts}")
    print(f"Source health passed: {counts}", flush=True)
    return counts


def live_playlist_ids():
    """Read exactly one named TIDAL playlist; reject ambiguity and auth failures."""
    import tidalapi
    session = tidalapi.Session()
    if not session.login_session_file(tp.SESSION_FILE):
        raise RuntimeError("TIDAL login failed; retaining playlist")
    playlists = [p for p in session.user.playlists() if str(p.id) == PLAYLIST_ID]
    if len(playlists) != 1:
        raise RuntimeError(f"Expected playlist ID {PLAYLIST_ID}, found {len(playlists)}")
    playlist = playlists[0]
    if playlist.name != "Down with the Kids":
        raise RuntimeError(f"Playlist ID matches but name changed to {playlist.name!r}; manual review required")
    ids = []
    for offset in range(0, 10000, 100):
        batch = playlist.tracks(limit=100, offset=offset)
        if not isinstance(batch, list):
            raise RuntimeError("TIDAL returned unverifiable playlist contents")
        ids.extend(str(track.id) for track in batch)
        if len(batch) < 100:
            return ids
    raise RuntimeError("TIDAL playlist exceeds safe read limit")


def verify_live_baseline(expected):
    actual = live_playlist_ids()
    if actual != [str(x) for x in expected]:
        raise RuntimeError(
            f"Live Down with the Kids differs from saved baseline "
            f"(live={len(actual)}, baseline={len(expected)}); no changes made")
    print(f"Live TIDAL baseline verified: {len(actual)} tracks", flush=True)


def main(preview=False):
    if not preview and os.environ.get("TREND_PLAYLIST_AUTO_PUBLISH") != "YES":
        raise RuntimeError("Set TREND_PLAYLIST_AUTO_PUBLISH=YES explicitly to enable unattended writes")
    if not STATE.exists():
        raise RuntimeError("Missing trusted baseline. Run: python auto_refresh.py --bootstrap")
    previous = json.loads(STATE.read_text(encoding="utf-8"))
    if previous.get("playlist_id") not in (None, PLAYLIST_ID):
        raise RuntimeError("Saved baseline references a different playlist ID")
    if previous.get("playlist_name") not in ("Down with the Kids", "UK Trends"):
        raise RuntimeError("Unexpected baseline playlist")
    if previous.get("playlist_name") == "UK Trends":
        print("Migrating saved baseline name to Down with the Kids after live verification", flush=True)
    verify_live_baseline(previous["track_ids"])
    if previous["playlist_name"] == "UK Trends":
        previous["playlist_name"] = "Down with the Kids"
        if not preview:
            save_state(previous)
    verify_source_health()
    # No stale review/approved file can be published if sweep or apply fails.
    run("sweep", "--official-chart", "--spotify-mirror", "--musicbrainz")
    review = tp.read_csv(tp.REVIEW)
    market_rows = sum(any(x in (r.get("signals") or "") for x in ("chart#", "apple#", "spotify#", "tiktok#"))
                      for r in review)
    chart_rows = sum("chart#" in (r.get("signals") or "") for r in review)
    apple_rows = sum("apple#" in (r.get("signals") or "") for r in review)
    spotify_rows = sum("spotify#" in (r.get("signals") or "") for r in review)
    healthy_sources = sum(n >= MIN_MARKET_ROWS for n in
                          (chart_rows, apple_rows, spotify_rows))
    if healthy_sources < 2:
        raise RuntimeError(
            f"Insufficient independent chart sources (chart={chart_rows}, "
            f"apple={apple_rows}, spotify={spotify_rows}); retaining existing playlist")
    if market_rows < MIN_MARKET_ROWS:
        raise RuntimeError("Insufficient chart data; retaining existing playlist")
    run("apply")
    run("push", "--name", "Down with the Kids", "--dry-run")
    report = tp.read_csv(tp.MATCH_REPORT)
    if not report or any(r.get("status") != "matched" or r.get("decision") == "reject"
                         for r in report):
        raise RuntimeError("Unresolved TIDAL match; retaining existing playlist")
    proposed = [r["tidal_id"] for r in report]
    # Generate an independently matched reserve pool for phone exclusions.
    # Preserve the verified 50-track files even if reserve matching fails.
    if preview:
        approved_bytes = tp.APPROVED.read_bytes()
        report_bytes = tp.MATCH_REPORT.read_bytes()
        try:
            run("apply", "--size", "80")
            run("push", "--name", "Down with the Kids", "--dry-run")
            reserve = tp.read_csv(tp.MATCH_REPORT)
            valid = [r for r in reserve if r.get("status") == "matched"
                     and r.get("decision") != "reject" and r.get("tidal_id")]
            tp.write_csv(tp.DATA / "phone_candidate_pool.csv", tp.MATCH_FIELDS, valid)
            print(f"Phone reserve: {len(valid)} verified matched candidates", flush=True)
        except Exception as exc:
            print(f"warning: phone reserve unavailable: {exc}", flush=True)
            (tp.DATA / "phone_candidate_pool.csv").unlink(missing_ok=True)
        finally:
            tp.APPROVED.write_bytes(approved_bytes)
            tp.MATCH_REPORT.write_bytes(report_bytes)
    changes = verify_plan(previous["track_ids"], proposed, market_rows)
    print(f"Verified changes: +{len(changes['added'])}, -{len(changes['removed'])}", flush=True)
    if preview:
        print("PREVIEW ONLY: no TIDAL playlist changes; local review/approved/match CSVs were refreshed.", flush=True)
        print("Added TIDAL IDs: " + (", ".join(changes["added"]) or "(none)"), flush=True)
        print("Removed TIDAL IDs: " + (", ".join(changes["removed"]) or "(none)"), flush=True)
        return
    if proposed == previous["track_ids"]:
        print("No changes; leaving playlist untouched")
        return
    # Recheck just before mutation to detect edits during a long sweep.
    verify_live_baseline(previous["track_ids"])
    # The push re-matches, but must reproduce the exact dry-run IDs before creating anything.
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=tp.DATA,
                                     prefix=".locked-tidal-plan-", suffix=".json",
                                     delete=False) as handle:
        plan_path = Path(handle.name)
        json.dump(proposed, handle)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        run("push", "--name", "Down with the Kids", "--replace",
            "--expected-ids-file", str(plan_path))
    finally:
        plan_path.unlink(missing_ok=True)
    save_state({"playlist_name": "Down with the Kids", "track_ids": proposed,
                "updated_at": datetime.now(timezone.utc).isoformat()})
    print("Published. Review TIDAL if network failed after a successful replacement.")



def refresh_baseline_from_live():
    """Explicit manual reconciliation only; never modifies a TIDAL playlist."""
    if not STATE.is_file():
        raise RuntimeError("No saved baseline to reconcile; use supervised bootstrap")
    previous = json.loads(STATE.read_text(encoding="utf-8"))
    if previous.get("playlist_id") not in (None, PLAYLIST_ID):
        raise RuntimeError("Saved baseline references another playlist ID")
    if previous.get("playlist_name") not in ("Down with the Kids", "UK Trends"):
        raise RuntimeError("Unexpected saved playlist name; refusing to reconcile")
    old = [str(x) for x in previous.get("track_ids", [])]
    if len(old) < MIN_TRACKS or len(set(old)) != len(old):
        raise RuntimeError("Saved baseline invalid; manual inspection required")
    live = live_playlist_ids()
    if len(live) < MIN_TRACKS or len(set(live)) != len(live):
        raise RuntimeError("Live playlist empty, too short or contains duplicates; refusing")
    print(f"Verified playlist ID: {PLAYLIST_ID}", flush=True)
    print(f"Saved baseline: {len(old)} tracks; live playlist: {len(live)} tracks", flush=True)
    print(f"New live IDs: {', '.join(x for x in live if x not in set(old)) or '(none)'}", flush=True)
    print(f"Absent old IDs: {', '.join(x for x in old if x not in set(live)) or '(none)'}", flush=True)
    # Recheck to avoid snapshotting a playlist that changes during reconciliation.
    if live_playlist_ids() != live:
        raise RuntimeError("Live playlist changed during verification; no baseline update")
    backup = STATE.with_name(STATE.stem + ".backup-" +
                             datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    with backup.open("x", encoding="utf-8") as target:
        json.dump(previous, target, indent=2)
        target.flush()
        os.fsync(target.fileno())
    save_state({"playlist_name": "Down with the Kids", "playlist_id": PLAYLIST_ID,
                "track_ids": live, "updated_at": datetime.now(timezone.utc).isoformat()})
    print(f"Old baseline backed up: {backup}", flush=True)
    print(f"Baseline reconciled to {len(live)} verified live tracks. TIDAL was NOT modified.", flush=True)


def bootstrap():
    """Record a known-good local match report only after user checks TIDAL manually."""
    report = tp.read_csv(tp.MATCH_REPORT)
    if len(report) < MIN_TRACKS or any(r.get("status") != "matched" for r in report):
        raise RuntimeError("A clean match report with at least 20 tracks is required")
    if STATE.exists():
        raise RuntimeError("Baseline already exists; refusing to overwrite it")
    verify_live_baseline([r["tidal_id"] for r in report])
    STATE.parent.mkdir(parents=True, exist_ok=True)
    save_state({"playlist_name": "Down with the Kids", "playlist_id": PLAYLIST_ID,
                "track_ids": [r["tidal_id"] for r in report],
                "updated_at": datetime.now(timezone.utc).isoformat()})
    print("Baseline saved after verifying exact live Down with the Kids contents.")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--refresh-baseline-from-live"]:
            refresh_baseline_from_live()
        elif sys.argv[1:] == ["--bootstrap"]:
            bootstrap()
        elif sys.argv[1:] == ["--preview"]:
            main(preview=True)
        elif not sys.argv[1:]:
            main()
        else:
            raise RuntimeError("Usage: python auto_refresh.py [--preview|--bootstrap|--refresh-baseline-from-live]")
    except Exception as exc:
        print(f"SAFE STOP: {exc}", file=sys.stderr)
        sys.exit(1)
