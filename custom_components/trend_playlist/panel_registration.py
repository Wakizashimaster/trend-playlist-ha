"""Trendee read-only sidebar panel registration for Home Assistant.

Milestone A deliberately uses only existing HA entity state in the browser.
No worker token, TIDAL credentials, or mutation endpoints are exposed.
"""
from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig

PANEL_PATH = "trendee"
STATIC_URL = "/trendee_static/trendee-panel.js"


async def async_register_trendee_panel(hass):
    path = Path(__file__).parent / "panel" / "trendee-panel.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(path), cache_headers=False)]
    )
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="trendee-panel",
        frontend_url_path=PANEL_PATH,
        module_url=STATIC_URL,
        sidebar_title="Trendee",
        sidebar_icon="mdi:music-circle",
        require_admin=False,
    )


async def async_unregister_trendee_panel(hass):
    hass.components.frontend.async_remove_panel(PANEL_PATH)
