"""Test Azure Storage Queue setup and entities."""

from unittest.mock import AsyncMock, patch

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)
import pytest

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.util.dt import utcnow

from tests.common import async_capture_events, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry, mock_queue_client
) -> None:
    """Test setup creates the sensor and unload closes the client."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) == 1
    assert states[0].state == STATE_UNKNOWN

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_queue_client.close.assert_awaited_once()


async def test_malformed_connection_string(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test malformed connection strings raise a config entry error."""
    from custom_components.azure_storage_queue import async_setup_entry  # noqa: PLC0415

    with (
        patch(
            "custom_components.azure_storage_queue.QueueClient.from_connection_string",
            side_effect=ValueError,
        ),
        pytest.raises(ConfigEntryError),
    ):
        await async_setup_entry(hass, mock_config_entry)


@pytest.mark.parametrize(
    ("side_effect", "raised_exception"),
    [
        (ClientAuthenticationError(), ConfigEntryAuthFailed),
        (ResourceNotFoundError(), ConfigEntryError),
        (HttpResponseError(), ConfigEntryNotReady),
        (ServiceRequestError("offline"), ConfigEntryNotReady),
        (TimeoutError(), ConfigEntryNotReady),
    ],
)
async def test_queue_property_errors(
    hass: HomeAssistant,
    mock_config_entry,
    mock_queue_client,
    side_effect: Exception,
    raised_exception: type[Exception],
) -> None:
    """Test queue property errors map to config entry exceptions."""
    from custom_components.azure_storage_queue import async_setup_entry  # noqa: PLC0415

    mock_queue_client.get_queue_properties.side_effect = side_effect
    with pytest.raises(raised_exception):
        await async_setup_entry(hass, mock_config_entry)


async def test_message_updates_sensor(
    hass: HomeAssistant, mock_config_entry, mock_queue_client
) -> None:
    """Test a dequeued message updates the sensor and fires an event."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        EVENT_AZURE_STORAGE_QUEUE,
        SCAN_INTERVAL,
    )

    payload = {"msg": "hello", "value": 1}
    events = async_capture_events(hass, EVENT_AZURE_STORAGE_QUEUE)
    with patch(
        "custom_components.azure_storage_queue.coordinator.dequeue_message",
        new=AsyncMock(side_effect=[None, ("message-id", payload)]),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()

    state = hass.states.async_all("sensor")[0]
    assert state.state == "hello"
    assert state.attributes["value"] == 1
    assert len(events) == 1
    assert events[0].data == payload


async def test_duplicate_message_is_ignored(
    hass: HomeAssistant, mock_config_entry, mock_queue_client
) -> None:
    """Test duplicate message IDs do not fire duplicate events."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        EVENT_AZURE_STORAGE_QUEUE,
        SCAN_INTERVAL,
    )

    payload = {"msg": "hello"}
    events = async_capture_events(hass, EVENT_AZURE_STORAGE_QUEUE)
    with patch(
        "custom_components.azure_storage_queue.coordinator.dequeue_message",
        new=AsyncMock(
            side_effect=[("message-id", payload), ("message-id", {"msg": "new"})]
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()

    state = hass.states.async_all("sensor")[0]
    assert state.state == "hello"
    assert len(events) == 1


async def test_long_message_is_truncated(
    hass: HomeAssistant, mock_config_entry, mock_queue_client
) -> None:
    """Test long message text is truncated to the state limit."""
    payload = {"msg": "x" * 300}
    with patch(
        "custom_components.azure_storage_queue.coordinator.dequeue_message",
        new=AsyncMock(return_value=("message-id", payload)),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.async_all("sensor")[0]
    assert len(state.state) == 255
    assert state.state.endswith("...")
