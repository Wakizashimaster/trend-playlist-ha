"""Offline safety tests: python -m unittest discover -s tests -p 'test_manual_reconciliation.py'"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trend_playlist_preview" / "app"))
from manual_reconciliation import reconcile, next_exclusions

BASE = [str(i) for i in range(100, 150)]

class ManualReconciliationTests(unittest.TestCase):
    def test_removal_excludes(self):
        result = reconcile(BASE, BASE[:-1], [])
        self.assertEqual(result.removed_ids, ("149",))
        self.assertEqual(next_exclusions([], result), {"149"})

    def test_readd_unblocks(self):
        result = reconcile(BASE[:-1], BASE, ["149"])
        self.assertEqual(result.restored_ids, ("149",))
        self.assertEqual(next_exclusions(["149"], result), set())

    def test_other_exclusions_survive(self):
        result = reconcile(BASE, BASE, ["999"])
        self.assertEqual(next_exclusions(["999"], result), {"999"})

    def test_reorder_is_not_removal(self):
        result = reconcile(BASE, list(reversed(BASE)), [])
        self.assertTrue(result.reordered)
        self.assertFalse(result.removed_ids)

    def test_manual_addition(self):
        result = reconcile(BASE, BASE + ["150"], [])
        self.assertEqual(result.added_ids, ("150",))

    def test_truncated_read_fails(self):
        with self.assertRaises(ValueError):
            reconcile(BASE, BASE[:5], [])

    def test_duplicate_read_fails(self):
        with self.assertRaises(ValueError):
            reconcile(BASE, BASE[:-1] + [BASE[-2]], [])

    def test_bulk_changes_fail(self):
        with self.assertRaises(ValueError):
            reconcile(BASE, BASE[:30] + [str(i) for i in range(200, 220)], [])

if __name__ == "__main__":
    unittest.main()
