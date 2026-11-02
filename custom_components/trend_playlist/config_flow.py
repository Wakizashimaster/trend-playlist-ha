"""Configure connection to the local read-only worker."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN

class TrendPlaylistFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            url = user_input["url"].rstrip("/")
            if not url.startswith("http://") and not url.startswith("https://"):
                errors["base"] = "invalid_url"
            else:
                try:
                    session = async_get_clientsession(self.hass)
                    async with session.get(url + "/status", headers={"Authorization": "Bearer " + user_input["token"]}, timeout=10) as response:
                        if response.status != 200:
                            raise ValueError("bad token or unavailable worker")
                    await self.async_set_unique_id("trend_playlist_worker")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Trend Playlist", data={"url": url, "token": user_input["token"]})
                except Exception:
                    errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("url", default="http://YOUR_PI_IP:8099"): str,
            vol.Required("token"): str,
        }), errors=errors)
