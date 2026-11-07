---
id: DOC-RB-NOTIFICATION-SERVICE
title: "Runbook: Notification Service"
doc_type: runbook
created_at: "2026-08-12T10:00:00Z"
author: Ahmed Hassan
services: [notification-service, email-dispatcher, event-bus]
---
# Runbook: Notification Service (notifier)

Owner: Customer Comms Team.

## Alerts

- **EmailVolumeAnomaly** - sends per minute below 20% of the forecast.
- **NotifierPodRestarts** - more than 3 restarts in 15 minutes.
- **NotifierConsumerLag** - lag on the order-events consumer group above 5,000.

## No notifications being sent

[[F-LINK-27|Order events are consumed from the Event Bus topic order-events.]] Check that the consumer group is assigned partitions and that `NOTIFY_ORDER_TOPIC` is `order-events`. After fixing, replay missed events with `notifyctl replay --since <timestamp>`.

## Delayed emails

[[F-LINK-28|Messages are handed to the Email Dispatcher queue.]] If that queue grows, see the Email Dispatcher dashboard and check MailRelay 429 responses.

## OOM restarts

Look at heap usage per pod. Caches must be bounded.
