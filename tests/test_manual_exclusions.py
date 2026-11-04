"""Offline tests for the reversible exclusion store."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trend_playlist_preview" / "app"))
from manual_exclusions import load, plan, atomic_write

PLAYLIST = "test-playlist-id"
BASE = [str(i) for i in range(100, 150)]

class ManualExclusionsTests(unittest.TestCase):
    def test_removal_survives_subsequent_unchanged_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_exclusions.json"
            store = load(path, PLAYLIST)
            result, next_store = plan(BASE, BASE[:-1], store)
            self.assertEqual(result.removed_ids, ("149",))
            atomic_write(path, next_store)
            stored = load(path, PLAYLIST)
            self.assertEqual(stored["excluded_ids"], ["149"])
            _, later = plan(BASE[:-1], BASE[:-1], stored)
            self.assertEqual(later["excluded_ids"], ["149"])
            self.assertEqual(len(later["events"]), 1)

    def test_readd_lifts_only_automatic_exclusion(self):
        store = {"schema": 1, "playlist_id": PLAYLIST,
                 "excluded_ids": ["149", "999"], "events": []}
        result, updated = plan(BASE[:-1], BASE, store)
        self.assertEqual(result.restored_ids, ("149",))
        self.assertEqual(updated["excluded_ids"], ["999"])
        self.assertEqual(updated["events"][0]["action"], "restored")

    def test_corrupt_store_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_exclusions.json"
            path.write_text('{"schema":1,"playlist_id":"wrong","excluded_ids":[],"events":[]}')
            with self.assertRaises(ValueError):
                load(path, PLAYLIST)

    def test_failed_plan_does_not_mutate_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_exclusions.json"
            atomic_write(path, load(path, PLAYLIST))
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                plan(BASE, BASE[:3], load(path, PLAYLIST))
            self.assertEqual(path.read_bytes(), before)

    def test_atomic_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "manual_exclusions.json"
            record = load(path, PLAYLIST)
            atomic_write(path, record)
            self.assertEqual(load(path, PLAYLIST), record)

if __name__ == "__main__":
    unittest.main()
