from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator, session = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PreviewButton(coordinator, session, entry)])

class PreviewButton(CoordinatorEntity, ButtonEntity):
    _attr_name = "Trend Playlist run preview"
    _attr_icon = "mdi:play-circle-outline"
    def __init__(self, coordinator, session, entry):
        super().__init__(coordinator)
        self.session, self.entry = session, entry
        self._attr_unique_id = entry.entry_id + "_run_preview"
    async def async_press(self):
        async with self.session.post(self.entry.data["url"] + "/preview",
            headers={"Authorization": "Bearer " + self.entry.data["token"]}, timeout=15) as response:
            response.raise_for_status()
        await self.coordinator.async_request_refresh()
