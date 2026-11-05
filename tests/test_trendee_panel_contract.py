"""Offline Milestone A safety/contract checks; no Home Assistant or TIDAL needed."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "custom_components/trend_playlist/panel/trendee-panel.js"
PY = ROOT / "custom_components/trend_playlist/panel_registration.py"

class TestPanelContract(unittest.TestCase):
    def test_read_only_panel(self):
        text = JS.read_text(encoding="utf-8")
        self.assertIn('sensor.trend_playlist_preview', text)
        self.assertIn("this._hass", text)
        self.assertNotIn("fetch(", text)
        self.assertNotIn("callService(", text)
        self.assertNotIn("publish_commit", text)
        self.assertNotIn("api_token", text)
        self.assertNotIn("tidalapi", text)

    def test_panel_registration_is_local(self):
        text = PY.read_text(encoding="utf-8")
        self.assertIn('frontend_url_path=PANEL_PATH', text)
        self.assertIn('module_url=STATIC_URL', text)
        self.assertIn('async_unregister_trendee_panel', text)

if __name__ == "__main__":
    unittest.main()
