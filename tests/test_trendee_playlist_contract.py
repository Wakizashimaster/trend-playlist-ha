"""Offline integration contract checks for the Milestone B read-only UI."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components/trend_playlist"


class PlaylistContractTests(unittest.TestCase):
    def test_dedicated_coordinator_and_entity(self):
        init = (INTEGRATION / "__init__.py").read_text()
        sensor = (INTEGRATION / "sensor.py").read_text()
        self.assertIn('"/playlist"', init)
        self.assertIn('timedelta(minutes=10)', init)
        self.assertIn('await playlist_coordinator.async_refresh()', init)
        self.assertIn('class PlaylistTracks(', sensor)
        self.assertIn('DOMAIN + "_playlist"', sensor)

    def test_browser_uses_only_home_assistant_state(self):
        js = (INTEGRATION / "panel/trendee-panel.js").read_text()
        self.assertIn('sensor.trendee_playlist_tracks', js)
        self.assertIn('class="search"', js)
        self.assertIn('data-search=', js)
        self.assertIn('rel="noopener noreferrer"', js)
        self.assertNotIn('Bearer ', js)
        self.assertNotIn('api_token', js)
        self.assertNotIn('fetch(', js)


if __name__ == "__main__":
    unittest.main()
