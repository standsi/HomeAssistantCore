"""Template sensor for Azure Storage Queue integration."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from . import QueueClientConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: QueueClientConfigEntry, async_add_entities
):
    """Set up the sensor platform."""
    async_add_entities([AzureStorageQueueSensor(entry)])
    return True


class AzureStorageQueueSensor(SensorEntity):
    """Represent an Azure Storage Queue as a Home Assistant sensor."""

    def __init__(self, entry: QueueClientConfigEntry) -> None:
        """Initialize the Azure Storage Queue sensor."""
        self._entry = entry
        self._state = None

    @property
    def name(self):
        """Return the sensor name."""
        return "Azure Storage Queue Sensor"

    @property
    def state(self):
        """Return the current sensor state."""
        return self._state
