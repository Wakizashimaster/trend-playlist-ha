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
        self.assertIn('esc(track.title', source)
        self.assertIn('esc(track.artist', source)

    def test_publish_requires_explicit_confirmation_and_matching_plan(self):
        source = PANEL.read_text()
        self.assertNotIn('"/publish_commit"', source)
        self.assertNotIn('"/approve"', source)
        self.assertNotIn('callService("button", "press", {entity_id: "button.trend_playlist_publish', source)
        self.assertIn('this._publishConfirmText !== "PUBLISH DOWN WITH THE KIDS"', source)
        self.assertIn('this._publishConfirmPlan !== plan', source)
        self.assertIn('!review.publish_preflight_passed', source)
        self.assertIn('!review.approval_recorded', source)
        self.assertIn('this._entity("button", "Trend Playlist Publish approved playlist")', source)
        self.assertIn('this._hass.callService("select", "select_option"', source)
        self.assertIn('review.decisions', source)


if __name__ == "__main__":
    unittest.main()
