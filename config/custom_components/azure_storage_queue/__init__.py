"""The Azure Storage Queue integration."""

from dataclasses import dataclass

# get the queue client
from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.storage.queue.aio import QueueClient
import probatio

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_MESSAGE, DOMAIN, QUEUENAME, SEND_QUEUENAME, SERVICE_SEND_MESSAGE
from .coordinator import AzureStorageQueueCoordinator
from .enqueue_message import enqueue_message

# List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
_PLATFORMS: list[Platform] = [Platform.SENSOR]

_SEND_MESSAGE_SCHEMA = probatio.Schema(
    {
        probatio.Optional(ATTR_DEVICE_ID): cv.string,
        probatio.Required(ATTR_MESSAGE): cv.string,
    }
)


@dataclass
class AzureStorageQueueData:
    """Runtime data for an Azure Storage Queue config entry."""

    coordinator: AzureStorageQueueCoordinator | None
    send_queue_client: QueueClient | None


# Create ConfigEntry type alias with API object
type AzureStorageQueueConfigEntry = ConfigEntry[AzureStorageQueueData]


async def _async_create_queue_client(connstring: str, queue_name: str) -> QueueClient:
    """Create a queue client and verify the queue is reachable."""
    try:
        queue_client = QueueClient.from_connection_string(
            conn_str=connstring,
            queue_name=queue_name,
        )
    except ValueError as err:
        raise ConfigEntryError("Malformed Azure Storage connection string") from err

    try:
        await queue_client.get_queue_properties()
    except ClientAuthenticationError as err:
        raise ConfigEntryAuthFailed("Invalid connection string") from err
    except ResourceNotFoundError as err:
        raise ConfigEntryError(f"Queue '{queue_name}' does not exist") from err
    except (HttpResponseError, ServiceRequestError, TimeoutError) as err:
        raise ConfigEntryNotReady("Cannot connect to Azure Storage Queue") from err

    return queue_client


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register Azure Storage Queue services."""

    def _async_get_target_entry(device_id: str | None) -> AzureStorageQueueConfigEntry:
        """Resolve the entry to send on, from an explicit device or the sole candidate."""
        if device_id is not None:
            device = dr.async_get(hass).async_get(device_id)
            if device is None:
                raise ServiceValidationError(f"Device '{device_id}' not found")

            entry_id = next(iter(device.config_entries), None)
            entry = hass.config_entries.async_get_entry(entry_id) if entry_id else None
            if entry is None or entry.domain != DOMAIN:
                raise ServiceValidationError(
                    f"Device '{device_id}' is not an Azure Storage Queue device"
                )
            return entry

        candidates = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state is ConfigEntryState.LOADED
            and entry.runtime_data.send_queue_client is not None
        ]
        if not candidates:
            raise ServiceValidationError(
                "No Azure Storage Queue entry has a send queue configured"
            )
        if len(candidates) > 1:
            raise ServiceValidationError(
                "Multiple Azure Storage Queue entries have a send queue configured; "
                "target a device to disambiguate"
            )
        return candidates[0]

    async def async_handle_send_message(call: ServiceCall) -> None:
        """Send a message to the send queue of the targeted (or sole) entry."""
        entry = _async_get_target_entry(call.data.get(ATTR_DEVICE_ID))
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(f"Entry '{entry.title}' is not loaded")

        send_queue_client = entry.runtime_data.send_queue_client
        if send_queue_client is None:
            raise ServiceValidationError(
                f"Entry '{entry.title}' does not have a send queue configured"
            )

        await enqueue_message(send_queue_client, {"msg": call.data[ATTR_MESSAGE]})

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        async_handle_send_message,
        schema=_SEND_MESSAGE_SCHEMA,
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: AzureStorageQueueConfigEntry
) -> bool:
    """Set up Azure Storage Queue from a config entry."""

    connstring = entry.data["connstring"]
    receive_queue_name = entry.data.get(QUEUENAME)
    send_queue_name = entry.data.get(SEND_QUEUENAME)

    coordinator: AzureStorageQueueCoordinator | None = None
    platforms: list[Platform] = []
    if receive_queue_name:
        queue_client = await _async_create_queue_client(connstring, receive_queue_name)
        coordinator = AzureStorageQueueCoordinator(hass, entry, queue_client)
        await coordinator.async_config_entry_first_refresh()
        platforms.append(Platform.SENSOR)

    send_queue_client: QueueClient | None = None
    if send_queue_name:
        send_queue_client = await _async_create_queue_client(
            connstring, send_queue_name
        )

    entry.runtime_data = AzureStorageQueueData(
        coordinator=coordinator, send_queue_client=send_queue_client
    )

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
    )

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AzureStorageQueueConfigEntry
) -> bool:
    """Unload a config entry."""
    platforms = [Platform.SENSOR] if entry.runtime_data.coordinator else []
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        if entry.runtime_data.coordinator:
            await entry.runtime_data.coordinator.queue_client.close()
        if entry.runtime_data.send_queue_client:
            await entry.runtime_data.send_queue_client.close()
    return unload_ok
