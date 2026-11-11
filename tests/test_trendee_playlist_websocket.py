"""Offline behavioral tests for the authenticated playlist WebSocket handler.

These tests stub Home Assistant's decorator surface; no HA runtime or TIDAL
account is required. Live Home Assistant verification remains a release gate.
"""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components/trend_playlist/playlist_websocket.py"


class Connection:
    def __init__(self):
        self.results = []
        self.errors = []

    def send_result(self, request_id, data):
        self.results.append((request_id, data))

    def send_error(self, request_id, code, message):
        self.errors.append((request_id, code, message))


class WebSocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import only the module under test, without importing HA or the
        # custom integration's full package initializer.
        websocket_api = types.ModuleType("homeassistant.components.websocket_api")
        websocket_api.websocket_command = lambda schema: lambda f: f
        websocket_api.async_response = lambda f: f
        homeassistant = types.ModuleType("homeassistant")
        homeassistant.__path__ = []
        components = types.ModuleType("homeassistant.components")
        components.__path__ = []
        components.websocket_api = websocket_api
        package = types.ModuleType("custom_components")
        package.__path__ = []
        integration = types.ModuleType("custom_components.trend_playlist")
        integration.__path__ = [str(MODULE.parent)]
        const = types.ModuleType("custom_components.trend_playlist.const")
        const.DOMAIN = "trend_playlist"
        cls.previous = {key: sys.modules.get(key) for key in (
            "homeassistant", "homeassistant.components",
            "homeassistant.components.websocket_api", "custom_components",
            "custom_components.trend_playlist",
            "custom_components.trend_playlist.const",
            "custom_components.trend_playlist.playlist_websocket",
        )}
        sys.modules.update({
            "homeassistant": homeassistant,
            "homeassistant.components": components,
            "homeassistant.components.websocket_api": websocket_api,
            "custom_components": package,
            "custom_components.trend_playlist": integration,
            "custom_components.trend_playlist.const": const,
        })
        spec = importlib.util.spec_from_file_location(
            "custom_components.trend_playlist.playlist_websocket", MODULE)
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.previous.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value

    def test_unconfigured_returns_error(self):
        conn = Connection()
        asyncio.run(self.module.websocket_playlist(types.SimpleNamespace(data={"trend_playlist_playlist": {}}), conn, {"id": 7}))
        self.assertEqual(conn.results, [])
        self.assertEqual(conn.errors[0][:2], (7, "not_ready"))

    def test_failed_refresh_returns_error_without_stale_tracks(self):
        conn = Connection()
        coordinator = types.SimpleNamespace(last_update_success=False, data={"tracks": ["stale"]})
        asyncio.run(self.module.websocket_playlist(
            types.SimpleNamespace(data={"trend_playlist_playlist": {"entry": coordinator}}), conn, {"id": 8}))
        self.assertEqual(conn.results, [])
        self.assertEqual(conn.errors[0][:2], (8, "unavailable"))

    def test_success_returns_only_public_playlist_fields(self):
        conn = Connection()
        data = {
            "playlist_id": "id", "playlist_name": "name",
            "source": "live_tidal_read_only", "track_count": 1,
            "tracks": [{"title": "A"}],
            "api_token": "NEVER_SEND", "session_file": "/private",
        }
        coordinator = types.SimpleNamespace(last_update_success=True, data=data)
        asyncio.run(self.module.websocket_playlist(
            types.SimpleNamespace(data={"trend_playlist_playlist": {"entry": coordinator}}), conn, {"id": 9}))
        self.assertEqual(conn.errors, [])
        self.assertEqual(conn.results, [(9, {
            "playlist_id": "id", "playlist_name": "name",
            "source": "live_tidal_read_only", "track_count": 1,
            "tracks": [{"title": "A"}],
        })])

    def test_registration_is_idempotent(self):
        hass = types.SimpleNamespace(data={})
        self.module.websocket_api.async_register_command = Mock()
        self.module.async_register_playlist_websocket(hass)
        self.module.async_register_playlist_websocket(hass)
        self.module.websocket_api.async_register_command.assert_called_once()


if __name__ == "__main__":
    unittest.main()
