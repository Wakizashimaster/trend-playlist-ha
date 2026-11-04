"""Offline tests for the read-only preview inspection boundary."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / "trend_playlist_preview" / "app"
sys.path.insert(0, str(APP))
# auto_refresh imports trend_playlist, which has normal pure-Python dependencies
# supplied by the app runtime. These tests do not authenticate or contact TIDAL.
import auto_refresh as ar

BASE = [str(i) for i in range(100, 150)]

class PreviewInspectionTests(unittest.TestCase):
    def test_manual_removal_is_inspected_without_persisting(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            with patch.object(ar.tp, "DATA", data), patch.object(ar, "live_playlist_ids",
                    side_effect=[BASE[:-1], BASE[:-1]]):
                result, record = ar.inspect_manual_edits(BASE)
                self.assertEqual(result.removed_ids, ("149",))
                self.assertEqual(record["excluded_ids"], ["149"])
                self.assertFalse((data / "manual_tidal_exclusions.json").exists())
                self.assertFalse((data / "auto_refresh_state.json").exists())

    def test_concurrent_edit_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ar.tp, "DATA", Path(tmp)), patch.object(ar, "live_playlist_ids",
                    side_effect=[BASE, BASE[:-1]]):
                with self.assertRaisesRegex(RuntimeError, "changed between reads"):
                    ar.inspect_manual_edits(BASE)

    def test_unresolved_publish_journal_is_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "phone_publish_journal.json").write_text(
                json.dumps({"status": "needs_manual_recovery"}))
            with patch.object(ar.tp, "DATA", data), patch.object(ar, "live_playlist_ids") as read:
                with self.assertRaisesRegex(RuntimeError, "Unresolved publish journal"):
                    ar.inspect_manual_edits(BASE)
                read.assert_not_called()

if __name__ == "__main__":
    unittest.main()
