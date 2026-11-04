"""Offline unit tests for the TIDAL-ID exclusion safety gate."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trend_playlist_preview" / "app"))
import trend_playlist as tp
import manual_exclusions

class CandidateExclusionTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"artist": "Artist A", "title": "Song A", "tidal_id": "123"},
            {"artist": "Artist B", "title": "Song B", "tidal_id": "456"},
        ]

    def test_match_rejected_by_tidal_id(self):
        with self.assertRaisesRegex(RuntimeError, "manual exclusions"):
            tp.reject_manual_exclusions(self.rows, {"123"})

    def test_non_excluded_ids_allowed(self):
        tp.reject_manual_exclusions(self.rows, {"789"})

    def test_same_title_other_id_not_silently_blocked(self):
        # The feature uses precise IDs. Alias/song-identity policy needs a
        # separate decision and must not be invented during matching.
        tp.reject_manual_exclusions(
            [{"artist": "Artist A", "title": "Song A", "tidal_id": "999"}],
            {"123"})

    def test_invalid_store_does_not_disable_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_tidal_exclusions.json"
            path.write_text('{"schema":1,"playlist_id":"wrong","excluded_ids":[],"events":[]}')
            with patch.object(tp, "DATA", Path(tmp)):
                with self.assertRaises(ValueError):
                    tp.manual_excluded_track_ids()

    def test_persisted_exclusions_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_tidal_exclusions.json"
            manual_exclusions.atomic_write(path, {
                "schema": 1,
                "playlist_id": "ac2a24f5-a386-40cb-a637-ad9f89f32622",
                "excluded_ids": ["123"],
                "events": []})
            with patch.object(tp, "DATA", Path(tmp)):
                self.assertEqual(tp.manual_excluded_track_ids(), {"123"})

if __name__ == "__main__":
    unittest.main()
