# Customer notifications architecture

_Owner: Customer Comms Team. Revised 10 August 2026._

The Notification Service (notifier) is owned by Customer Comms, as is the Email Dispatcher.

## Event intake

Since 5 August 2026 the notifier consumes order lifecycle events from the Event Bus topic order-events. Until that date it received the same events through an HTTP webhook called by the Order Service. The webhook has been switched off and will be deleted.

## Sending

For every notification the notifier enqueues a message for the Email Dispatcher (mailer), which renders the template and hands it to MailRelay for delivery. Retries carry an idempotency key so duplicates are dropped by the mailer.

## Limits

MailRelay enforces an hourly quota per account. Campaign days need a quota increase requested in advance.
