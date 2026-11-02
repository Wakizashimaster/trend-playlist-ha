from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator, session = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PreviewButton(coordinator, session, entry), ApprovalButton(coordinator, session, entry, "custom"), ApprovalButton(coordinator, session, entry, "everything")])

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

class ApprovalButton(CoordinatorEntity, ButtonEntity):
    _attr_icon = "mdi:check-decagram-outline"
    def __init__(self, coordinator, session, entry, mode):
        super().__init__(coordinator)
        self.session, self.entry, self.mode = session, entry, mode
        self._attr_unique_id = entry.entry_id + "_approve_" + mode
        self._attr_name = "Trend Playlist " + ("Approve reviewed proposal" if mode == "custom" else "Approve Everything")
    @property
    def available(self):
        return super().available and self.coordinator.data.get("review", {}).get("ready", False)
    async def async_press(self):
        review = self.coordinator.data["review"]
        async with self.session.post(self.entry.data["url"] + "/approve",
            headers={"Authorization": "Bearer " + self.entry.data["token"]},
            json={"proposal_id": review["proposal_id"], "plan_hash": review["plan_hash"],
                  "mode": self.mode}, timeout=15) as response:
            response.raise_for_status()
        await self.coordinator.async_request_refresh()
