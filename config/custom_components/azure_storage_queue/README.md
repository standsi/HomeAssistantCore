# Azure Storage Queue Custom Integration

This custom integration supports:

- Receiving JSON messages from an Azure Storage Queue and firing the `azure_storage_queue_message` event.
- Sending payloads (string or structured JSON) to a configured send queue.
- Multiple config entries, each with one or both of:
  - `queuename` (receive queue)
  - `send_queuename` (send queue)

## Important Configuration Rules

### 1) Send and receive queue names in a single entry must differ

A single config entry cannot use the same queue name for both send and receive.

### 2) Duplicate receive queue configs are blocked (same account)

To avoid race conditions where one entry dequeues messages before another trigger sees them,
a second config entry with the same:

- Azure connection string, and
- receive queue name (`queuename`)

is rejected during config flow with an error.

If duplicate receive queue entries already exist from older configurations, setup logs a warning
that either entry may consume messages.

## Naming Behavior

Default generated names are:

- send-only: `<account>: <send_queue>`
- receive-only: `<account>: <receive_queue>`
- combined send+receive: `<account>: <send_queue> / <receive_queue>`

The combined naming helps disambiguate entries in automation selectors.

## Automation Trigger Options

### Device trigger (UI-friendly)

Use the device trigger type:

- `azure_storage_queue.message_received`

This is convenient in the visual editor, but it is tied to Home Assistant `device_id`.
If a device/config entry is deleted and recreated, `device_id` changes and existing device-trigger
automations must be reselected.

### YAML trigger (more stable across device recreation)

Use the custom trigger platform directly in YAML:

```yaml
triggers:
  - trigger: azure_storage_queue.message_received
    receive_queue_name: my-receive-queue
```

Supported trigger fields:

- `config_entry_id`
- `device_id`
- `receive_queue_name`

You can use one or combine them for stricter matching.

## Event Metadata

Receive events include source metadata under:

- `_azure_storage_queue`

with keys:

- `config_entry_id`
- `receive_queue_name`

Example template usage:

```jinja2
{{ trigger.event.data._azure_storage_queue.receive_queue_name }}
```
