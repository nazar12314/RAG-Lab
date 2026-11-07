---
id: DOC-ARCH-NOTIFICATIONS
title: Customer notifications architecture
doc_type: architecture
created_at: "2026-08-10T09:30:00Z"
author: Sofia Marquez
services: [notification-service, email-dispatcher, event-bus, order-service]
---
# Customer notifications architecture

_Owner: Customer Comms Team. Revised 10 August 2026._

[[F-OWNER-notification-service|The Notification Service (notifier) is owned by Customer Comms]], [[F-OWNER-email-dispatcher|as is the Email Dispatcher]].

## Event intake

[[F-LINK-27|Since 5 August 2026 the notifier consumes order lifecycle events from the Event Bus topic order-events.]] [[F-LINK-26|Until that date it received the same events through an HTTP webhook called by the Order Service.]] The webhook has been switched off and will be deleted.

## Sending

[[F-LINK-28|For every notification the notifier enqueues a message for the Email Dispatcher (mailer)]], [[F-LINK-29|which renders the template and hands it to MailRelay for delivery.]] Retries carry an idempotency key so duplicates are dropped by the mailer.

## Limits

MailRelay enforces an hourly quota per account. Campaign days need a quota increase requested in advance.
