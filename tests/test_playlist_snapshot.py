"""Offline checks for the read-only playlist endpoint (no TIDAL connection)."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "trend_playlist_preview/app/playlist_snapshot.py"
spec = importlib.util.spec_from_file_location("playlist_snapshot", PATH)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


class PlaylistSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.original = sys.modules.get("tidalapi")
        self.tidalapi = types.ModuleType("tidalapi")
        sys.modules["tidalapi"] = self.tidalapi

    def tearDown(self):
        if self.original is None:
            sys.modules.pop("tidalapi", None)
        else:
            sys.modules["tidalapi"] = self.original

    def test_live_order_and_metadata(self):
        track = types.SimpleNamespace(
            id=123, name="Example Song",
            artists=[types.SimpleNamespace(name="Example Artist")],
            album=types.SimpleNamespace(name="Example Album", image=lambda size: "https://example.test/cover.jpg"))
        playlist = types.SimpleNamespace(
            id=snapshot.PLAYLIST_ID, name=snapshot.PLAYLIST_NAME,
            tracks=lambda limit, offset: [track] if offset == 0 else [])
        session = MagicMock()
        session.login_session_file.return_value = True
        session.user.playlists.return_value = [playlist]
        self.tidalapi.Session = lambda: session
        result = snapshot.read_playlist(Path("/unused"))
        self.assertEqual(result["source"], "live_tidal_read_only")
        self.assertEqual(result["track_count"], 1)
        self.assertEqual(result["tracks"][0]["position"], 1)
        self.assertEqual(result["tracks"][0]["title"], "Example Song")
        self.assertEqual(result["tracks"][0]["artist"], "Example Artist")

    def test_rejects_playlist_identity_mismatch(self):
        session = MagicMock()
        session.login_session_file.return_value = True
        session.user.playlists.return_value = []
        self.tidalapi.Session = lambda: session
        with self.assertRaisesRegex(RuntimeError, "identity"):
            snapshot.read_playlist(Path("/unused"))

    def test_rejects_missing_authentication(self):
        session = MagicMock()
        session.login_session_file.return_value = False
        self.tidalapi.Session = lambda: session
        with self.assertRaisesRegex(RuntimeError, "authentication"):
            snapshot.read_playlist(Path("/unused"))

    def test_worker_can_import_modules_from_addon_app_directory(self):
        # Docker copies app/ to /opt/trend but executes /worker.py from /.
        dockerfile = (ROOT / "trend_playlist_preview/Dockerfile").read_text()
        worker = (ROOT / "trend_playlist_preview/worker.py").read_text()
        self.assertIn("COPY app/ /opt/trend/", dockerfile)
        self.assertIn('CMD ["python3", "/worker.py"]', dockerfile)
        self.assertIn('ROOT = Path("/opt/trend")', worker)
        self.assertIn('sys.path.insert(0, str(ROOT))', worker)
        self.assertLess(worker.index('sys.path.insert(0, str(ROOT))'),
                        worker.index('from playlist_snapshot import read_playlist'))

    def test_worker_route_is_authenticated_and_get_only(self):
        worker = (ROOT / "trend_playlist_preview/worker.py").read_text()
        get_section = worker.split("    def do_GET(self):", 1)[1].split("    def do_POST(self):", 1)[0]
        self.assertLess(get_section.index("if not self.authorized():"), get_section.index('if self.path == "/playlist":'))
        self.assertIn('read_playlist(tp.SESSION_FILE)', get_section)
        self.assertIn('{"error": "Playlist temporarily unavailable"}', get_section)


if __name__ == "__main__":
    unittest.main()
