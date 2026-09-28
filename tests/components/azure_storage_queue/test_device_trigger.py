"""Tests for Azure Storage Queue device triggers."""

import pytest

from homeassistant.components import automation
from homeassistant.components.device_automation import (
    DeviceAutomationType,
    InvalidDeviceAutomationConfig,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_get_device_automations

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry,
    mock_queue_client,
) -> None:
    """Test we get the expected triggers."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        DOMAIN,
        MESSAGE_RECEIVED_TRIGGER,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None

    expected = {
        "platform": "device",
        "domain": DOMAIN,
        "type": MESSAGE_RECEIVED_TRIGGER,
        "device_id": device.id,
        "metadata": {},
    }

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected in triggers


async def test_if_fires_on_matching_event(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    mock_config_entry,
    mock_queue_client,
) -> None:
    """Test the device trigger fires when the matching entry receives a message."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        ATTR_CONFIG_ENTRY_ID,
        ATTR_SOURCE_METADATA,
        DOMAIN,
        EVENT_AZURE_STORAGE_QUEUE,
        MESSAGE_RECEIVED_TRIGGER,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": MESSAGE_RECEIVED_TRIGGER,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "device_id": "{{ trigger.device_id }}",
                            "entry": "{{ trigger.config_entry_id }}",
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_AZURE_STORAGE_QUEUE,
        {
            "msg": "hello",
            ATTR_SOURCE_METADATA: {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            },
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["device_id"] == device.id
    assert service_calls[0].data["entry"] == mock_config_entry.entry_id


async def test_invalid_trigger_raises(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry,
    mock_queue_client,
) -> None:
    """Test invalid trigger platform or device id raises."""
    from custom_components.azure_storage_queue import device_trigger  # noqa: PLC0415
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        DOMAIN,
        MESSAGE_RECEIVED_TRIGGER,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await device_trigger.async_attach_trigger(
            hass,
            {
                CONF_TYPE: "wrong.type",
                CONF_DEVICE_ID: "invalid-device-id",
            },
            None,
            {},
        )

    with pytest.raises(InvalidDeviceAutomationConfig) as exc_info:
        await device_trigger.async_validate_trigger_config(
            hass,
            {
                CONF_PLATFORM: "device",
                "domain": DOMAIN,
                CONF_TYPE: MESSAGE_RECEIVED_TRIGGER,
                CONF_DEVICE_ID: "invalid-device-id",
            },
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "device_not_valid"


@pytest.mark.parametrize(
    ("domain", "entry_state", "expected_translation_key"),
    [
        (
            "azure_storage_queue",
            ConfigEntryState.NOT_LOADED,
            "device_config_entry_not_loaded",
        ),
        ("fake", ConfigEntryState.LOADED, "device_not_valid"),
    ],
)
async def test_invalid_entry_raises(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    domain: str,
    entry_state: ConfigEntryState,
    expected_translation_key: str,
) -> None:
    """Test device id from invalid or unloaded entries raises."""
    from custom_components.azure_storage_queue import device_trigger  # noqa: PLC0415
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        DOMAIN,
        MESSAGE_RECEIVED_TRIGGER,
    )

    entry = MockConfigEntry(domain=domain, state=entry_state, data={})
    entry.runtime_data = None
    entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("fake", "fake")}
    )

    with pytest.raises(InvalidDeviceAutomationConfig) as exc_info:
        await device_trigger.async_validate_trigger_config(
            hass,
            {
                CONF_PLATFORM: "device",
                "domain": DOMAIN,
                CONF_TYPE: MESSAGE_RECEIVED_TRIGGER,
                CONF_DEVICE_ID: device.id,
            },
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == expected_translation_key
