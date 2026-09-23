"""Read and dequeue a single message from an Azure Storage Queue."""

import base64
import binascii
import json
import logging

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.queue.aio import QueueClient

from .const import SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Comfortably longer than SCAN_INTERVAL so a slow delete can't let the
# message become visible (and redelivered) again before it's removed.
VISIBILITY_TIMEOUT = int(SCAN_INTERVAL.total_seconds()) * 3


async def dequeue_message(queue_client: QueueClient) -> tuple[str, dict] | None:
    """Read the first available message from the queue and delete it on success.

    Args:
        queue_client: The Azure Storage Queue client to read from.

    Returns:
        A (message_id, payload) tuple, where payload is the decoded JSON
        (e.g. {"date": ..., "msg": ...}), if a message was retrieved and
        successfully dequeued, otherwise None.

    Raises:
        Any azure connectivity/authentication error raised by `receive_message`
        (e.g. HttpResponseError, ServiceRequestError, ClientAuthenticationError)
        propagates to the caller so no message is reported as dequeued.
    """
    message = await queue_client.receive_message(visibility_timeout=VISIBILITY_TIMEOUT)
    if message is None:
        return None

    try:
        decoded_content = base64.b64decode(message.content, validate=True).decode(
            "utf-8"
        )
        payload = json.loads(decoded_content)
    except binascii.Error, ValueError, UnicodeDecodeError, json.JSONDecodeError:
        _LOGGER.error("Queue message content is not valid JSON: %r", message.content)
        payload = None

    try:
        await queue_client.delete_message(message)
    except ResourceNotFoundError:
        # Message was already deleted/expired (e.g. visibility timeout elapsed).
        _LOGGER.warning("Message already removed from queue before it could be deleted")
        return None

    if payload is None:
        # Malformed message: already removed above, nothing to report.
        return None

    return message.id, payload
