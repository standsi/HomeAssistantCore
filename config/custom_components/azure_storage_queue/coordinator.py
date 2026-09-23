"""Coordinator for the Azure Storage Queue integration."""

import logging
from typing import TYPE_CHECKING

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ServiceRequestError,
)
from azure.storage.queue.aio import QueueClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, EVENT_AZURE_STORAGE_QUEUE, SCAN_INTERVAL
from .dequeue_message import dequeue_message

if TYPE_CHECKING:
    from . import AzureStorageQueueConfigEntry

_LOGGER = logging.getLogger(__name__)


class AzureStorageQueueCoordinator(DataUpdateCoordinator[dict | None]):
    """Coordinator that polls a queue and fires an event for each new message."""

    config_entry: AzureStorageQueueConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AzureStorageQueueConfigEntry,
        queue_client: QueueClient,
    ) -> None:
        """Initialize the coordinator."""
        self.queue_client = queue_client
        self._last_message_id: str | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict | None:
        """Dequeue the next message and fire an event for it, if any."""
        try:
            result = await dequeue_message(self.queue_client)
        except (
            ClientAuthenticationError,
            HttpResponseError,
            ServiceRequestError,
        ) as err:
            raise UpdateFailed(
                f"Error fetching from Azure Storage Queue: {err}"
            ) from err

        if result is None:
            # Keep reporting the last dequeued message until a new one arrives.
            return self.data

        message_id, payload = result
        if message_id == self._last_message_id:
            # Same message redelivered (e.g. delete raced the visibility timeout).
            _LOGGER.warning(
                "Skipping duplicate delivery of already-processed message %s",
                message_id,
            )
            return self.data

        self._last_message_id = message_id
        self.hass.bus.async_fire(EVENT_AZURE_STORAGE_QUEUE, payload)
        return payload
