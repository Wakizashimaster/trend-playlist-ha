"""Read-only, authenticated TIDAL playlist snapshot for the Trendee panel.

This module never calls playlist mutation methods. It is invoked only by
the worker's bearer-token-protected GET /playlist route.
"""
from pathlib import Path

PLAYLIST_ID = "ac2a24f5-a386-40cb-a637-ad9f89f32622"
PLAYLIST_NAME = "Down with the Kids"
MAX_TRACKS = 500


def read_playlist(session_file: Path):
    import tidalapi

    session = tidalapi.Session()
    if not session.login_session_file(session_file):
        raise RuntimeError("TIDAL authentication unavailable")
    matches = [p for p in session.user.playlists() if str(p.id) == PLAYLIST_ID]
    if len(matches) != 1 or matches[0].name != PLAYLIST_NAME:
        raise RuntimeError("Protected playlist identity could not be verified")

    playlist = matches[0]
    tracks = []
    for offset in range(0, MAX_TRACKS + 1, 100):
        batch = playlist.tracks(limit=100, offset=offset)
        if not isinstance(batch, list):
            raise RuntimeError("TIDAL returned invalid playlist data")
        for track in batch:
            if len(tracks) >= MAX_TRACKS:
                raise RuntimeError("Playlist exceeds the read-only display limit")
            album = getattr(track, "album", None)
            artists = getattr(track, "artists", None) or []
            artist = " / ".join(str(a.name) for a in artists if getattr(a, "name", None))
            if not artist:
                artist = str(getattr(getattr(track, "artist", None), "name", ""))
            artwork = None
            if album is not None:
                try:
                    artwork = album.image(160)
                except (AttributeError, ValueError, TypeError):
                    pass
            tracks.append({
                "position": len(tracks) + 1,
                "tidal_id": str(track.id),
                "title": str(getattr(track, "name", "")),
                "artist": artist,
                "album": str(getattr(album, "name", "") or ""),
                "artwork_url": artwork if isinstance(artwork, str) and artwork.startswith("https://") else None,
                "tidal_url": f"https://tidal.com/browse/track/{track.id}",
            })
        if len(batch) < 100:
            return {
                "playlist_id": PLAYLIST_ID,
                "playlist_name": PLAYLIST_NAME,
                "source": "live_tidal_read_only",
                "track_count": len(tracks),
                "tracks": tracks,
            }
    raise RuntimeError("Playlist exceeds the read-only display limit")
