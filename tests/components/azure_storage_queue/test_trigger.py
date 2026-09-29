"""Tests for Azure Storage Queue triggers."""

import pytest

from homeassistant.components import automation
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_event_trigger_fires_for_matching_config_entry(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_config_entry,
    mock_queue_client,
) -> None:
    """Test trigger fires when event metadata matches the targeted config entry."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        ATTR_CONFIG_ENTRY_ID,
        ATTR_SOURCE_METADATA,
        EVENT_AZURE_STORAGE_QUEUE,
        MESSAGE_RECEIVED_TRIGGER,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": MESSAGE_RECEIVED_TRIGGER,
                        ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "message": "{{ trigger.event.data.msg }}",
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
    assert service_calls[0].data["message"] == "hello"
    assert service_calls[0].data["entry"] == mock_config_entry.entry_id


async def test_event_trigger_ignores_non_matching_config_entry(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_config_entry,
    mock_queue_client,
) -> None:
    """Test trigger does not fire for a different config entry id."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        ATTR_CONFIG_ENTRY_ID,
        ATTR_SOURCE_METADATA,
        EVENT_AZURE_STORAGE_QUEUE,
        MESSAGE_RECEIVED_TRIGGER,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": MESSAGE_RECEIVED_TRIGGER,
                        ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                    },
                    "action": {"service": "test.automation"},
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
                ATTR_CONFIG_ENTRY_ID: "different-entry",
            },
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 0


async def test_event_trigger_fires_for_matching_device(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    mock_config_entry,
    mock_queue_client,
) -> None:
    """Test trigger configured by device id resolves and fires for matching entry."""
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
                        "platform": MESSAGE_RECEIVED_TRIGGER,
                        CONF_DEVICE_ID: device.id,
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_AZURE_STORAGE_QUEUE,
        {
            ATTR_SOURCE_METADATA: {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            },
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_event_trigger_fires_for_matching_queue_name(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_config_entry,
    mock_queue_client,
) -> None:
    """Test trigger can target messages by receive queue name only."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        ATTR_CONFIG_ENTRY_ID,
        ATTR_RECEIVE_QUEUE_NAME,
        ATTR_SOURCE_METADATA,
        EVENT_AZURE_STORAGE_QUEUE,
        MESSAGE_RECEIVED_TRIGGER,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": MESSAGE_RECEIVED_TRIGGER,
                        ATTR_RECEIVE_QUEUE_NAME: "messages",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "queue": "{{ trigger.receive_queue_name }}",
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
            ATTR_SOURCE_METADATA: {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_RECEIVE_QUEUE_NAME: "messages",
            },
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["queue"] == "messages"


async def test_event_trigger_ignores_non_matching_queue_name(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_config_entry,
    mock_queue_client,
) -> None:
    """Test queue-name trigger ignores events from other receive queues."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        ATTR_CONFIG_ENTRY_ID,
        ATTR_RECEIVE_QUEUE_NAME,
        ATTR_SOURCE_METADATA,
        EVENT_AZURE_STORAGE_QUEUE,
        MESSAGE_RECEIVED_TRIGGER,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": MESSAGE_RECEIVED_TRIGGER,
                        ATTR_RECEIVE_QUEUE_NAME: "messages",
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_AZURE_STORAGE_QUEUE,
        {
            ATTR_SOURCE_METADATA: {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_RECEIVE_QUEUE_NAME: "different-queue",
            },
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 0
