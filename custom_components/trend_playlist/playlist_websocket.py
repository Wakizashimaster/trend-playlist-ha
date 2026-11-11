"""Authenticated Home Assistant WebSocket read of cached playlist data.

The browser receives no worker token and the track list never enters entity
attributes, state history or recorder. This endpoint cannot mutate TIDAL.
"""
from homeassistant.components import websocket_api
from .const import DOMAIN

COMMAND = "trendee/playlist"


@websocket_api.websocket_command({"type": COMMAND})
@websocket_api.async_response
async def websocket_playlist(hass, connection, msg):
    playlists = hass.data.get(DOMAIN + "_playlist", {})
    if not playlists:
        connection.send_error(msg["id"], "not_ready", "Trendee playlist is not configured")
        return

    # One playlist is supported. Never leak the worker URL or bearer token.
    coordinator = next(iter(playlists.values()))
    if not coordinator.last_update_success or not coordinator.data:
        connection.send_error(msg["id"], "unavailable", "Live playlist is temporarily unavailable")
        return

    data = coordinator.data
    connection.send_result(msg["id"], {
        "playlist_id": data["playlist_id"],
        "playlist_name": data["playlist_name"],
        "source": data["source"],
        "track_count": data["track_count"],
        "tracks": data["tracks"],
    })


def async_register_playlist_websocket(hass):
    """Register once per Home Assistant runtime, including config-entry reloads."""
    key = DOMAIN + "_playlist_websocket_registered"
    if hass.data.get(key):
        return
    websocket_api.async_register_command(hass, websocket_playlist)
    hass.data[key] = True
