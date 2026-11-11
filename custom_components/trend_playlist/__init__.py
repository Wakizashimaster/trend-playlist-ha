"""Read-only Home Assistant connection to the Trend Playlist worker."""
from datetime import timedelta
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN
from .playlist_websocket import async_register_playlist_websocket
from .panel_registration import async_register_trendee_panel, async_unregister_trendee_panel

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button", "select"]

async def async_setup_entry(hass, entry):
    session = async_get_clientsession(hass)
    async def update():
        try:
            async with session.get(entry.data["url"] + "/status",
                headers={"Authorization": "Bearer " + entry.data["token"]}, timeout=15) as response:
                response.raise_for_status()
                status = await response.json()
            try:
                async with session.get(entry.data["url"] + "/review",
                    headers={"Authorization": "Bearer " + entry.data["token"]}, timeout=15) as review_response:
                    if review_response.status == 200:
                        status["review"] = await review_response.json()
            except Exception as exc:
                _LOGGER.debug("Review endpoint unavailable: %s", exc)
            return status
        except Exception as exc:
            raise UpdateFailed(str(exc)) from exc
    async def update_playlist():
        try:
            async with session.get(entry.data["url"] + "/playlist",
                headers={"Authorization": "Bearer " + entry.data["token"]}, timeout=30) as response:
                response.raise_for_status()
                payload = await response.json()
            if (payload.get("playlist_id") != "ac2a24f5-a386-40cb-a637-ad9f89f32622"
                    or payload.get("source") != "live_tidal_read_only"
                    or not isinstance(payload.get("tracks"), list)):
                raise ValueError("Unverified playlist response")
            return payload
        except Exception as exc:
            raise UpdateFailed("Read-only playlist unavailable") from exc

    playlist_coordinator = DataUpdateCoordinator(hass, _LOGGER, name="Trendee playlist",
        update_method=update_playlist, update_interval=timedelta(minutes=10))
    # A failed playlist fetch must never prevent the existing integration from loading.
    await playlist_coordinator.async_refresh()
    hass.data.setdefault(DOMAIN + "_playlist", {})[entry.entry_id] = playlist_coordinator
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="Trend Playlist",
        update_method=update, update_interval=timedelta(seconds=30))
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        hass.data[DOMAIN + "_playlist"].pop(entry.entry_id, None)
        raise
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = (coordinator, session)
    async_register_playlist_websocket(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if len(hass.data[DOMAIN]) == 1:
        try:
            await async_register_trendee_panel(hass)
        except Exception:
            _LOGGER.exception("Unable to register Trendee sidebar panel")
    return True

async def async_unload_entry(hass, entry):
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.data.get(DOMAIN + "_playlist", {}).pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            await async_unregister_trendee_panel(hass)
    return ok
