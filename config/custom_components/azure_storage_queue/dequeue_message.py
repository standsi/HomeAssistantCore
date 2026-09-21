"""Read and dequeue a single message from an Azure Storage Queue."""

import base64
import json
import logging

from azure.core.exceptions import ResourceNotFoundError

from . import QueueClientConfigEntry

logger = logging.getLogger(__name__)


def dequeue_message(entry: QueueClientConfigEntry) -> dict | None:
    """Read the first available message from the queue and delete it on success.

    Args:
        entry: QueueClientConfigEntry containing the connection string and queue name.

    Returns:
        The decoded JSON payload (e.g. {"date": ..., "msg": ...}) if a message
        was retrieved and successfully dequeued, otherwise None.
    """
    queue_client = entry.runtime_data

    messages = queue_client.receive_messages(messages_per_page=1)
    message = next(iter(messages), None)
    if message is None:
        return None

    try:
        decoded_content = base64.b64decode(message.content, validate=True).decode(
            "utf-8"
        )
        payload = json.loads(decoded_content)
    except TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError:
        logger.error("Queue message content is not valid JSON: %r", message.content)
        return None

    try:
        queue_client.delete_message(message)
    except ResourceNotFoundError:
        # Message was already deleted/expired (e.g. visibility timeout elapsed).
        logger.warning("Message already removed from queue before it could be deleted")
        return None

    return payload
