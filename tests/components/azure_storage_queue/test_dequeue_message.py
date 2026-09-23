"""Test Azure Storage Queue message handling."""

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

from azure.core.exceptions import ResourceNotFoundError, ServiceRequestError
import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_no_message() -> None:
    """Test an empty queue."""
    from custom_components.azure_storage_queue.dequeue_message import (  # noqa: PLC0415
        dequeue_message,
    )

    queue_client = SimpleNamespace(
        receive_message=AsyncMock(return_value=None),
        delete_message=AsyncMock(),
    )

    assert await dequeue_message(queue_client) is None
    queue_client.delete_message.assert_not_awaited()


async def test_valid_message() -> None:
    """Test decoding and deleting a valid message."""
    from custom_components.azure_storage_queue.dequeue_message import (  # noqa: PLC0415
        dequeue_message,
    )

    message = SimpleNamespace(
        id="message-id",
        content=base64.b64encode(b'{"msg": "hello", "value": 1}'),
    )
    queue_client = SimpleNamespace(
        receive_message=AsyncMock(return_value=message),
        delete_message=AsyncMock(),
    )

    assert await dequeue_message(queue_client) == (
        "message-id",
        {"msg": "hello", "value": 1},
    )
    queue_client.delete_message.assert_awaited_once_with(message)


@pytest.mark.parametrize(
    "content",
    [
        b"not-base64",
        base64.b64encode(b"not-utf8: \xff"),
        base64.b64encode(b"not-json"),
    ],
)
async def test_invalid_message(content: bytes) -> None:
    """Test malformed messages are deleted and ignored."""
    from custom_components.azure_storage_queue.dequeue_message import (  # noqa: PLC0415
        dequeue_message,
    )

    message = SimpleNamespace(id="message-id", content=content)
    queue_client = SimpleNamespace(
        receive_message=AsyncMock(return_value=message),
        delete_message=AsyncMock(),
    )

    assert await dequeue_message(queue_client) is None
    queue_client.delete_message.assert_awaited_once_with(message)


async def test_message_already_deleted() -> None:
    """Test a message deleted before the delete request completes."""
    from custom_components.azure_storage_queue.dequeue_message import (  # noqa: PLC0415
        dequeue_message,
    )

    message = SimpleNamespace(id="message-id", content=base64.b64encode(b"{}"))
    queue_client = SimpleNamespace(
        receive_message=AsyncMock(return_value=message),
        delete_message=AsyncMock(side_effect=ResourceNotFoundError()),
    )

    assert await dequeue_message(queue_client) is None


async def test_receive_error() -> None:
    """Test receive errors propagate to the coordinator."""
    from custom_components.azure_storage_queue.dequeue_message import (  # noqa: PLC0415
        dequeue_message,
    )

    queue_client = SimpleNamespace(
        receive_message=AsyncMock(side_effect=ServiceRequestError("offline")),
        delete_message=AsyncMock(),
    )

    with pytest.raises(ServiceRequestError):
        await dequeue_message(queue_client)
    queue_client.delete_message.assert_not_awaited()
