"""Pure ranked refill tests, no TIDAL or network access."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trend_playlist_preview" / "app"))
import trend_playlist as tp

def rows(n):
    return [{"artist": f"Artist {i}", "title": f"Song {i}",
             "tidal_id": str(1000+i), "status": "matched", "decision": ""}
            for i in range(n)]

class RefillTests(unittest.TestCase):
    def test_refills_two_exclusions(self):
        selected = tp.refill_from_ranked_matches(rows(80), {"1000", "1001"})
        self.assertEqual(len(selected), 50)
        self.assertEqual(selected[0]["tidal_id"], "1002")
        self.assertEqual(selected[-1]["tidal_id"], "1051")

    def test_no_exclusions_preserves_top_fifty(self):
        selected = tp.refill_from_ranked_matches(rows(80), set())
        self.assertEqual([r["tidal_id"] for r in selected],
                         [r["tidal_id"] for r in rows(50)])

    def test_not_enough_eligible_fails(self):
        with self.assertRaisesRegex(RuntimeError, "cannot safely refill"):
            tp.refill_from_ranked_matches(rows(50), {"1000"})

    def test_unmatched_and_review_are_skipped(self):
        candidates = rows(52)
        candidates[0]["status"] = "review"
        candidates[1]["status"] = "unmatched"
        selected = tp.refill_from_ranked_matches(candidates, set())
        self.assertEqual(len(selected), 50)
        self.assertEqual(selected[0]["tidal_id"], "1002")

    def test_duplicate_ids_not_repeated(self):
        candidates = rows(51)
        candidates[1]["tidal_id"] = candidates[0]["tidal_id"]
        selected = tp.refill_from_ranked_matches(candidates, set())
        self.assertEqual(len({r["tidal_id"] for r in selected}), 50)

if __name__ == "__main__":
    unittest.main()
