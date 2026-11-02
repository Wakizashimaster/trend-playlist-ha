"""Phone-friendly per-song review choices; never publishes to TIDAL."""
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

OPTIONS = ["Keep", "Exclude this week", "Promote to Zeitgeist", "Block from future proposals"]
TO_ACTION = dict(zip(OPTIONS, ("keep", "exclude", "zeitgeist", "block")))
FROM_ACTION = {v: k for k, v in TO_ACTION.items()}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator, session = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ReviewChoice(coordinator, session, entry, i) for i in range(50)] +
                       [RemovalChoice(coordinator, session, entry, i) for i in range(50)])

class ReviewChoice(CoordinatorEntity, SelectEntity):
    _attr_icon = "mdi:playlist-edit"
    _attr_options = OPTIONS

    def __init__(self, coordinator, session, entry, index):
        super().__init__(coordinator)
        self.session, self.entry, self.index = session, entry, index
        self._attr_unique_id = entry.entry_id + "_review_" + str(index)

    @property
    def item(self):
        additions = self.coordinator.data.get("review", {}).get("additions", [])
        return additions[self.index] if self.index < len(additions) else None

    @property
    def available(self):
        return super().available and self.item is not None

    @property
    def name(self):
        item = self.item
        return ("Review: " + item["artist"] + " – " + item["title"]) if item else "Review slot " + str(self.index + 1)

    @property
    def current_option(self):
        item = self.item
        if not item:
            return None
        decision = self.coordinator.data.get("review", {}).get("decisions", {}).get(item["tidal_id"], "keep")
        return FROM_ACTION.get(decision, "Keep")

    @property
    def extra_state_attributes(self):
        return dict(self.item or {})

    async def async_select_option(self, option):
        item = self.item
        review = self.coordinator.data.get("review", {})
        if item is None or option not in TO_ACTION or not review.get("proposal_id"):
            raise ValueError("No current proposal")
        async with self.session.post(self.entry.data["url"] + "/decision",
            headers={"Authorization": "Bearer " + self.entry.data["token"]},
            json={"proposal_id": review["proposal_id"], "tidal_id": item["tidal_id"],
                  "action": TO_ACTION[option]}, timeout=15) as response:
            response.raise_for_status()
        await self.coordinator.async_request_refresh()

class RemovalChoice(CoordinatorEntity, SelectEntity):
    _attr_icon = "mdi:playlist-remove"
    _attr_options = ["Remove as proposed", "Retain in playlist"]
    def __init__(self, coordinator, session, entry, index):
        super().__init__(coordinator)
        self.session, self.entry, self.index = session, entry, index
        self._attr_unique_id = entry.entry_id + "_removal_" + str(index)
    @property
    def item(self):
        items = self.coordinator.data.get("review", {}).get("removals", [])
        return items[self.index] if self.index < len(items) else None
    @property
    def available(self):
        return super().available and self.item is not None
    @property
    def name(self):
        item = self.item
        return "Removal: " + (item.get("title") or item["tidal_id"]) if item else "Removal slot " + str(self.index + 1)
    @property
    def current_option(self):
        if not self.item:
            return None
        decision = self.coordinator.data.get("review", {}).get("decisions", {}).get(self.item["tidal_id"])
        return "Retain in playlist" if decision == "retain" else "Remove as proposed"
    @property
    def extra_state_attributes(self):
        return dict(self.item or {})
    async def async_select_option(self, option):
        if not self.item or option not in self._attr_options:
            raise ValueError("Invalid removal choice")
        review = self.coordinator.data["review"]
        async with self.session.post(self.entry.data["url"] + "/decision",
            headers={"Authorization": "Bearer " + self.entry.data["token"]},
            json={"proposal_id": review["proposal_id"], "tidal_id": self.item["tidal_id"],
                  "action": "retain" if option == "Retain in playlist" else "remove"}, timeout=15) as response:
            response.raise_for_status()
        await self.coordinator.async_request_refresh()
