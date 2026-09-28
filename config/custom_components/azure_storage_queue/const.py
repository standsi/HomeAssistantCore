"""Constants for the Azure Storage Queue integration."""

from datetime import timedelta

DOMAIN = "azure_storage_queue"
CONNSTRING = "connstring"
ACCTNAME = "acctname"
QUEUENAME = "queuename"
SEND_QUEUENAME = "send_queuename"

ATTR_MESSAGE = "message"

SERVICE_SEND_MESSAGE = "send_message"

EVENT_AZURE_STORAGE_QUEUE = "azure_storage_queue_message"
SCAN_INTERVAL = timedelta(seconds=30)
