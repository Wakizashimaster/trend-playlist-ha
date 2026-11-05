"""Read-only Home Assistant connection to the Trend Playlist worker."""
from datetime import timedelta
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN
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
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="Trend Playlist",
        update_method=update, update_interval=timedelta(seconds=30))
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = (coordinator, session)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if len(hass.data[DOMAIN]) == 1:
        await async_register_trendee_panel(hass)
    return True

async def async_unload_entry(hass, entry):
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            await async_unregister_trendee_panel(hass)
    return ok
