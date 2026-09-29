"""Provides device triggers for Azure Storage Queue."""

import probatio

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import trigger
from .const import DOMAIN, MESSAGE_RECEIVED_TRIGGER

TRIGGER_TYPES = {MESSAGE_RECEIVED_TRIGGER}
TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_TYPE): probatio.In(TRIGGER_TYPES),
    }
)


def async_get_message_received_trigger(device_id: str) -> dict[str, str]:
    """Return trigger data for a queue message received trigger."""
    return {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: MESSAGE_RECEIVED_TRIGGER,
    }


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    if config[CONF_TYPE] == MESSAGE_RECEIVED_TRIGGER:
        device_id = config[CONF_DEVICE_ID]
        _, config_entry = dr.async_get_device_and_config_entry_for_domain(
            hass, device_id, domain=DOMAIN
        )
        if config_entry is None:
            raise InvalidDeviceAutomationConfig(
                translation_domain=DOMAIN,
                translation_key="device_not_valid",
                translation_placeholders={"device_id": device_id},
            )
        if config_entry.state is not ConfigEntryState.LOADED:
            raise InvalidDeviceAutomationConfig(
                translation_domain=DOMAIN,
                translation_key="device_config_entry_not_loaded",
                translation_placeholders={"device_id": device_id},
            )

    return config


async def async_get_triggers(
    _hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for device."""
    return [async_get_message_received_trigger(device_id)]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    if (trigger_type := config[CONF_TYPE]) == MESSAGE_RECEIVED_TRIGGER:
        trigger_config = {
            CONF_PLATFORM: trigger_type,
            CONF_DEVICE_ID: config[CONF_DEVICE_ID],
        }
        trigger_config = await trigger.async_validate_trigger_config(
            hass, trigger_config
        )
        return await trigger.async_attach_trigger(
            hass, trigger_config, action, trigger_info
        )

    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="unhandled_trigger_type",
        translation_placeholders={"trigger_type": trigger_type},
    )
