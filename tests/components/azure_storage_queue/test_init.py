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
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed

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


async def test_send_only_entry_has_no_sensor(
    hass: HomeAssistant, mock_queue_client
) -> None:
    """Test an entry with only a send queue creates no sensor entity."""
    from custom_components.azure_storage_queue.const import DOMAIN  # noqa: PLC0415

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "connstring": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key",
            "send_queuename": "outbox",
            "acctname": "test",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.async_all("sensor") == []
    assert entry.runtime_data.coordinator is None
    assert entry.runtime_data.send_queue_client is mock_queue_client


async def test_send_message_service(
    hass: HomeAssistant,
    mock_config_entry,
    mock_queue_client,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the send_message service enqueues a message onto the device's entry."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        DOMAIN,
        SEND_QUEUENAME,
        SERVICE_SEND_MESSAGE,
    )

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, SEND_QUEUENAME: "outbox"},
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {"device_id": device.id, "message": "hello"},
        blocking=True,
    )

    mock_queue_client.send_message.assert_awaited_once()


async def test_send_message_service_unknown_device(
    hass: HomeAssistant, mock_config_entry, mock_queue_client
) -> None:
    """Test the send_message service rejects an unknown device."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        DOMAIN,
        SERVICE_SEND_MESSAGE,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {"device_id": "unknown-device", "message": "hello"},
            blocking=True,
        )


async def test_send_message_service_no_send_queue(
    hass: HomeAssistant,
    mock_config_entry,
    mock_queue_client,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the send_message service rejects an entry without a send queue."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        DOMAIN,
        SERVICE_SEND_MESSAGE,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {"device_id": device.id, "message": "hello"},
            blocking=True,
        )


async def test_send_message_service_no_device_id_single_entry(
    hass: HomeAssistant, mock_config_entry, mock_queue_client
) -> None:
    """Test the service auto-resolves the sole entry with a send queue configured."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        DOMAIN,
        SEND_QUEUENAME,
        SERVICE_SEND_MESSAGE,
    )

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, SEND_QUEUENAME: "outbox"},
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {"message": "hello"},
        blocking=True,
    )

    mock_queue_client.send_message.assert_awaited_once()


async def test_send_message_service_no_device_id_no_send_queue(
    hass: HomeAssistant, mock_config_entry, mock_queue_client
) -> None:
    """Test the service rejects an omitted device when no entry has a send queue."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        DOMAIN,
        SERVICE_SEND_MESSAGE,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {"message": "hello"},
            blocking=True,
        )


async def test_send_message_service_no_device_id_ambiguous(
    hass: HomeAssistant, mock_config_entry, mock_queue_client
) -> None:
    """Test the service rejects an omitted device when multiple entries qualify."""
    from custom_components.azure_storage_queue.const import (  # noqa: PLC0415
        DOMAIN,
        SEND_QUEUENAME,
        SERVICE_SEND_MESSAGE,
    )

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, SEND_QUEUENAME: "outbox"},
    )
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "connstring": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key",
            "send_queuename": "outbox2",
            "acctname": "test",
        },
    )
    other_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {"message": "hello"},
            blocking=True,
        )
