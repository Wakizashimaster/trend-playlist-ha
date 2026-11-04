"""Offline tests for journalled local manual-edit reconciliation."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trend_playlist_preview" / "app"))
import auto_refresh as ar
import manual_exclusions as exclusions

BASE = [str(i) for i in range(100, 150)]
PLAYLIST = ar.PLAYLIST_ID

class ReconciliationCommitTests(unittest.TestCase):
    def test_commit_removal_then_readd(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            previous = {"playlist_id": PLAYLIST, "playlist_name": "Down with the Kids",
                        "track_ids": BASE}
            with patch.object(ar.tp, "DATA", data), patch.object(ar, "STATE", data / "auto_refresh_state.json"):
                store = exclusions.load(data / "manual_tidal_exclusions.json", PLAYLIST)
                result, updated = exclusions.plan(BASE, BASE[:-1], store)
                with patch.object(ar, "live_playlist_ids", return_value=BASE[:-1]):
                    next_state = ar.commit_manual_reconciliation(previous, result, updated)
                self.assertEqual(next_state["track_ids"], BASE[:-1])
                self.assertEqual(exclusions.load(data / "manual_tidal_exclusions.json", PLAYLIST)["excluded_ids"], ["149"])
                self.assertFalse((data / "manual_reconciliation_pending.json").exists())
                result2, updated2 = exclusions.plan(BASE[:-1], BASE, exclusions.load(data / "manual_tidal_exclusions.json", PLAYLIST))
                with patch.object(ar, "live_playlist_ids", return_value=BASE):
                    restored = ar.commit_manual_reconciliation(next_state, result2, updated2)
                self.assertEqual(restored["track_ids"], BASE)
                self.assertEqual(exclusions.load(data / "manual_tidal_exclusions.json", PLAYLIST)["excluded_ids"], [])

    def test_live_drift_rejected_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            previous = {"playlist_id": PLAYLIST, "track_ids": BASE}
            result, updated = exclusions.plan(BASE, BASE[:-1], exclusions.load(data / "manual_tidal_exclusions.json", PLAYLIST))
            with patch.object(ar.tp, "DATA", data), patch.object(ar, "live_playlist_ids", return_value=BASE):
                with self.assertRaisesRegex(RuntimeError, "changed before"):
                    ar.commit_manual_reconciliation(previous, result, updated)
            self.assertFalse((data / "manual_tidal_exclusions.json").exists())

    def test_unresolved_marker_blocks_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "manual_reconciliation_pending.json").write_text("{}")
            previous = {"playlist_id": PLAYLIST, "track_ids": BASE}
            result, updated = exclusions.plan(BASE, BASE[:-1], exclusions.load(data / "manual_tidal_exclusions.json", PLAYLIST))
            with patch.object(ar.tp, "DATA", data):
                with self.assertRaisesRegex(RuntimeError, "Unresolved"):
                    ar.commit_manual_reconciliation(previous, result, updated)

if __name__ == "__main__":
    unittest.main()
