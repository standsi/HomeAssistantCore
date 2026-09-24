"""Template sensor for Azure Storage Queue integration."""

import json

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AzureStorageQueueConfigEntry
from .coordinator import AzureStorageQueueCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzureStorageQueueConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities([AzureStorageQueueSensor(entry)])


class AzureStorageQueueSensor(
    CoordinatorEntity[AzureStorageQueueCoordinator], SensorEntity
):
    """Represent the last message dequeued from an Azure Storage Queue."""

    _attr_has_entity_name = True
    _attr_translation_key = "queue_message"

    def __init__(self, entry: AzureStorageQueueConfigEntry) -> None:
        """Initialize the Azure Storage Queue sensor."""
        super().__init__(entry.runtime_data.coordinator)
        self._attr_unique_id = f"{entry.entry_id}_queue_message"

    @property
    def native_value(self) -> str | None:
        """Return the message text of the last dequeued item, truncated to fit a state."""
        if self.coordinator.data is None:
            return None
        msg = json.dumps(self.coordinator.data)  # self.coordinator.data.get("msg")
        if isinstance(msg, str) and len(msg) > MAX_LENGTH_STATE_STATE:
            return msg[: MAX_LENGTH_STATE_STATE - 3] + "..."
        return msg

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the last dequeued message's payload."""
        return self.coordinator.data
