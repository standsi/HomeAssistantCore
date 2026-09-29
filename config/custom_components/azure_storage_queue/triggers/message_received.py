"""Azure Storage Queue message received trigger."""

from custom_components.azure_storage_queue.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_RECEIVE_QUEUE_NAME,
    ATTR_SOURCE_METADATA,
    DOMAIN,
    EVENT_AZURE_STORAGE_QUEUE,
    MESSAGE_RECEIVED_TRIGGER,
)
import probatio

from homeassistant.const import CONF_DEVICE_ID, CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

TRIGGER_SCHEMA = probatio.All(
    cv.TRIGGER_BASE_SCHEMA.extend(
        {
            probatio.Required(CONF_PLATFORM): MESSAGE_RECEIVED_TRIGGER,
            probatio.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
            probatio.Optional(ATTR_RECEIVE_QUEUE_NAME): cv.string,
            probatio.Optional(CONF_DEVICE_ID): cv.string,
        }
    ),
    cv.has_at_least_one_key(
        ATTR_CONFIG_ENTRY_ID, ATTR_RECEIVE_QUEUE_NAME, CONF_DEVICE_ID
    ),
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for Azure Storage Queue events based on target entry/device."""
    device_id: str | None = config.get(CONF_DEVICE_ID)
    target_entry_id: str | None = config.get(ATTR_CONFIG_ENTRY_ID)
    target_queue_name: str | None = config.get(ATTR_RECEIVE_QUEUE_NAME)

    if target_entry_id is None and device_id is not None:
        _, config_entry = dr.async_get_device_and_config_entry_for_domain(
            hass, device_id, domain=DOMAIN
        )
        if config_entry is None:
            return lambda: None
        target_entry_id = config_entry.entry_id

    trigger_data = trigger_info["trigger_data"]
    job = HassJob(action)

    async def handle_event(event: Event) -> None:
        """Handle queue message events and fire trigger when the entry matches."""
        source_metadata = event.data.get(ATTR_SOURCE_METADATA)
        if not isinstance(source_metadata, dict):
            return

        if (
            target_entry_id is not None
            and source_metadata.get(ATTR_CONFIG_ENTRY_ID) != target_entry_id
        ):
            return

        if (
            target_queue_name is not None
            and source_metadata.get(ATTR_RECEIVE_QUEUE_NAME) != target_queue_name
        ):
            return

        task = hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    CONF_PLATFORM: MESSAGE_RECEIVED_TRIGGER,
                    ATTR_CONFIG_ENTRY_ID: target_entry_id,
                    ATTR_RECEIVE_QUEUE_NAME: target_queue_name,
                    CONF_DEVICE_ID: device_id,
                    "event": event,
                    "description": "Azure Storage Queue message received",
                }
            },
            event.context,
        )

        if task:
            await task

    return hass.bus.async_listen(EVENT_AZURE_STORAGE_QUEUE, handle_event)
