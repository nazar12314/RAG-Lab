---
id: DOC-ADR-EVENT-BUS-MIGRATION
title: "ADR-019: Migrate notifications and inventory to the event bus"
doc_type: adr
created_at: "2026-07-10T11:00:00Z"
author: Kenji Watanabe
services: [notification-service, order-service, inventory-service, event-bus]
---
# ADR-019: Migrate notifications and inventory to the event bus

**Status:** Accepted. **Migration date:** 5 August 2026.

## Context

[[F-LINK-26|The Notification Service currently depends on an HTTP webhook from the Order Service.]] When the notifier is slow, the Order Service blocks, and webhook calls are lost during deploys.

## Decision

On 5 August 2026:

- [[F-LINK-27|The Notification Service will consume order events from the Event Bus instead of the webhook.]] The webhook will be disabled the same day.
- [[F-LINK-32|The Inventory Service will start publishing stock-changed events to the Event Bus.]]

## Consequences

- Event volume on the cluster is expected to roughly double. Capacity should be reviewed after the migration.
- Consumers must be idempotent because the bus guarantees at-least-once delivery.
