"""The Azure Storage Queue integration."""

# get the queue client
from azure.storage.queue.aio import QueueClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

# List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
_PLATFORMS: list[Platform] = [Platform.SENSOR]

# Create ConfigEntry type alias with API object
# Rename type alias and update all entry annotations
type QueueClientConfigEntry = ConfigEntry[QueueClient]


# Update entry annotation
async def async_setup_entry(hass: HomeAssistant, entry: QueueClientConfigEntry) -> bool:
    """Set up Azure Storage Queue from a config entry."""

    #  1. Create API instance
    #  2. Validate the API connection (and authentication)
    #  3. Store an API object for your platforms to access
    # entry.runtime_data = MyAPI(...)

    _connstring = entry.data["connstring"]
    _queue_name = entry.data["queuename"]
    queueclient = QueueClient.from_connection_string(
        conn_str=_connstring,
        queue_name=_queue_name,
    )
    entry.runtime_data = queueclient

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


#  Update entry annotation
async def async_unload_entry(
    hass: HomeAssistant, entry: QueueClientConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
