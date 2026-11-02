from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator, _ = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PreviewStatus(coordinator, entry.entry_id), ProposalReview(coordinator, entry.entry_id)])

class PreviewStatus(CoordinatorEntity, SensorEntity):
    _attr_name = "Trend Playlist preview"
    _attr_icon = "mdi:playlist-check"
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator)
        self._attr_unique_id = entry_id + "_preview"
    @property
    def native_value(self):
        data = self.coordinator.data
        return "running" if data.get("running") else ("success" if data.get("ok") else "failed" if data.get("ok") is False else "not run")
    @property
    def extra_state_attributes(self):
        return dict(self.coordinator.data)

class ProposalReview(CoordinatorEntity, SensorEntity):
    _attr_name = "Trend Playlist proposal"
    _attr_icon = "mdi:playlist-edit"
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator)
        self._attr_unique_id = entry_id + "_proposal"
    @property
    def native_value(self):
        review = self.coordinator.data.get("review", {})
        return "ready" if review.get("ready") else "unavailable"
    @property
    def extra_state_attributes(self):
        review = self.coordinator.data.get("review", {})
        if not review.get("ready"):
            return {"reason": review.get("reason", "Review not available yet")}
        return {k: v for k, v in review.items() if k != "review_candidates"}
