"""Encode and enqueue a message onto an Azure Storage Queue."""

import base64
import json

from azure.storage.queue.aio import QueueClient


async def enqueue_message(queue_client: QueueClient, payload: dict) -> None:
    """Encode payload as base64 JSON and send it to the queue.

    Uses the same framing `dequeue_message` decodes, so messages sent by this
    integration can also be read back by it.

    Raises:
        Any azure connectivity/authentication error raised by `send_message`
        (e.g. HttpResponseError, ServiceRequestError, ClientAuthenticationError)
        propagates to the caller.
    """
    content = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    await queue_client.send_message(content)
