"""Fixtures for Azure Storage Queue tests."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    "connstring": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key",
    "queuename": "messages",
    "acctname": "test",
}


@pytest.fixture
def hass_config_dir() -> str:
    """Use the repository config directory containing the custom integration."""
    return str(Path(__file__).parents[3] / "config")


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a configured Azure Storage Queue entry."""
    entry = MockConfigEntry(domain="azure_storage_queue", data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_queue_client() -> Generator[MagicMock]:
    """Mock the Azure Storage Queue client used by the integration."""
    with patch(
        "custom_components.azure_storage_queue.QueueClient",
        autospec=True,
    ) as queue_client:
        client = queue_client.from_connection_string.return_value
        client.get_queue_properties = AsyncMock()
        client.receive_message = AsyncMock(return_value=None)
        client.delete_message = AsyncMock()
        client.close = AsyncMock()
        yield client
