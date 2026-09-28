"""Constants for the Azure Storage Queue integration."""

from datetime import timedelta

DOMAIN = "azure_storage_queue"
CONNSTRING = "connstring"
ACCTNAME = "acctname"
QUEUENAME = "queuename"
SEND_QUEUENAME = "send_queuename"
MESSAGE_RECEIVED_TRIGGER = f"{DOMAIN}.message_received"

ATTR_MESSAGE = "message"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_RECEIVE_QUEUE_NAME = "receive_queue_name"
ATTR_SOURCE_METADATA = "_azure_storage_queue"

SERVICE_SEND_MESSAGE = "send_message"

EVENT_AZURE_STORAGE_QUEUE = "azure_storage_queue_message"
SCAN_INTERVAL = timedelta(seconds=30)
