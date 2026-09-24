"""Config flow for the Azure Storage Queue integration."""

import logging
from typing import Any

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import ACCTNAME, CONNSTRING, DOMAIN, QUEUENAME, SEND_QUEUENAME

_LOGGER = logging.getLogger(__name__)

#  adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONNSTRING): str,
        probatio.Optional(QUEUENAME): str,
        probatio.Optional(SEND_QUEUENAME): str,
        probatio.Required(ACCTNAME): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    receive_queue = data.get(QUEUENAME)
    send_queue = data.get(SEND_QUEUENAME)

    if not receive_queue and not send_queue:
        raise NoQueueConfigured

    if receive_queue and send_queue and receive_queue == send_queue:
        raise SameQueueName

    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data[CONF_USERNAME], data[CONF_PASSWORD]
    # )

    hub = PlaceholderHub(data[CONNSTRING])

    if not await hub.authenticate(data[ACCTNAME], receive_queue or send_queue):
        raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": "Name of the device"}


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure Storage Queue."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except NoQueueConfigured:
                errors["base"] = "no_queue_configured"
            except SameQueueName:
                errors["base"] = "same_queue_name"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


class NoQueueConfigured(Exception):
    """Error to indicate neither a receive nor a send queue name was given."""


class SameQueueName(Exception):
    """Error to indicate the receive and send queue names are the same."""
