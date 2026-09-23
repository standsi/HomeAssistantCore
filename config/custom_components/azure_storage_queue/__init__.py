"""The Azure Storage Queue integration."""

# get the queue client
from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.storage.queue.aio import QueueClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .coordinator import AzureStorageQueueCoordinator

# List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
_PLATFORMS: list[Platform] = [Platform.SENSOR]

# Create ConfigEntry type alias with API object
type AzureStorageQueueConfigEntry = ConfigEntry[AzureStorageQueueCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: AzureStorageQueueConfigEntry
) -> bool:
    """Set up Azure Storage Queue from a config entry."""

    _connstring = entry.data["connstring"]
    _queue_name = entry.data["queuename"]
    try:
        queueclient = QueueClient.from_connection_string(
            conn_str=_connstring,
            queue_name=_queue_name,
        )
    except ValueError as err:
        raise ConfigEntryError("Malformed Azure Storage connection string") from err

    try:
        await queueclient.get_queue_properties()
    except ClientAuthenticationError as err:
        raise ConfigEntryAuthFailed("Invalid connection string") from err
    except ResourceNotFoundError as err:
        raise ConfigEntryError(f"Queue '{_queue_name}' does not exist") from err
    except (HttpResponseError, ServiceRequestError, TimeoutError) as err:
        raise ConfigEntryNotReady("Cannot connect to Azure Storage Queue") from err

    coordinator = AzureStorageQueueCoordinator(hass, entry, queueclient)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AzureStorageQueueConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        await entry.runtime_data.queue_client.close()
    return unload_ok
