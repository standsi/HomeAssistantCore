"""Test the Azure Storage Queue config flow."""

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_form(hass: HomeAssistant) -> None:
    """Test the user form and successful entry creation."""
    from custom_components.azure_storage_queue.const import DOMAIN  # noqa: PLC0415

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == MOCK_CONFIG


async def test_form_no_queue_configured(hass: HomeAssistant) -> None:
    """Test the form is rejected when neither queue name is set."""
    from custom_components.azure_storage_queue.const import DOMAIN  # noqa: PLC0415

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    data = {key: value for key, value in MOCK_CONFIG.items() if key != "queuename"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_queue_configured"}


async def test_form_same_queue_name(hass: HomeAssistant) -> None:
    """Test the form is rejected when receive and send queue names match."""
    from custom_components.azure_storage_queue.const import DOMAIN  # noqa: PLC0415

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    data = {**MOCK_CONFIG, "send_queuename": MOCK_CONFIG["queuename"]}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "same_queue_name"}
