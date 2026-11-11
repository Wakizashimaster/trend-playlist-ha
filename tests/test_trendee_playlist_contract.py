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

    def test_websocket_keeps_tracks_out_of_recorder(self):
        sensor = (INTEGRATION / "sensor.py").read_text()
        websocket = (INTEGRATION / "playlist_websocket.py").read_text()
        init = (INTEGRATION / "__init__.py").read_text()
        self.assertNotIn('**self.coordinator.data', sensor)
        self.assertNotIn('"tracks": data["tracks"]', sensor)
        self.assertIn('"tracks": data["tracks"]', websocket)
        self.assertIn('@websocket_api.websocket_command', websocket)
        self.assertIn('async_register_playlist_websocket(hass)', init)

    def test_browser_uses_authenticated_home_assistant_websocket(self):
        js = (INTEGRATION / "panel/trendee-panel.js").read_text()
        self.assertIn('sensor.trendee_playlist_tracks', js)
        self.assertIn('callWS({type: "trendee/playlist"})', js)
        self.assertNotIn('pa.tracks', js)
        self.assertIn('class="search"', js)
        self.assertIn('data-search=', js)
        self.assertIn('rel="noopener noreferrer"', js)
        self.assertNotIn('Bearer ', js)
        self.assertNotIn('api_token', js)
        self.assertNotIn('fetch(', js)


if __name__ == "__main__":
    unittest.main()
