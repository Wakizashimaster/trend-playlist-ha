"""Offline safety checks for Trendee sidebar preview and review."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "custom_components/trend_playlist/panel/trendee-panel.js"


class PreviewReviewContractTests(unittest.TestCase):
    def test_sidebar_uses_existing_preview_button(self):
        source = PANEL.read_text()
        self.assertIn('"Trend Playlist run preview"', source)
        self.assertIn('this._hass.callService("button", "press"', source)
        self.assertIn('this._previewPending', source)
        self.assertIn('status?.attributes?.running === true', source)

    def test_review_is_derived_from_existing_status(self):
        source = PANEL.read_text()
        self.assertIn('const review = a.review || {}', source)
        self.assertIn('review.revised_additions', source)
        self.assertIn('review.revised_removals', source)
        self.assertIn('review.ready === true && !busy', source)
        self.assertIn('esc(t.title', source)
        self.assertIn('esc(t.artist', source)

    def test_no_publish_or_approval_actions_in_panel(self):
        source = PANEL.read_text()
        self.assertNotIn('"/publish_commit"', source)
        self.assertNotIn('"/approve"', source)
        self.assertNotIn('callService("button", "press", {entity_id: "button.trend_playlist_publish', source)
        self.assertIn("No action on this page can publish to TIDAL.", source)


if __name__ == "__main__":
    unittest.main()
