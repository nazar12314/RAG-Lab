---
id: DOC-RB-EVENT-BUS
title: "Runbook: Event Bus (Kafka)"
doc_type: runbook
created_at: "2026-07-12T10:00:00Z"
author: Kenji Watanabe
services: [event-bus, warehouse-loader, notification-service]
---
# Runbook: Event Bus (Kafka cluster)

Owner: Data Platform Team, #team-data.

## Alerts

- **BrokerDiskUsage** - any broker data volume above 85%.
- **ConsumerLagHigh** - any consumer group more than 30 minutes behind.
- **UnderReplicatedPartitions** - more than 0 for 10 minutes.

## Consumer lag

1. Check whether lag is growing for one group or all groups.
2. Frequent rebalances (look for `Revoking partitions` in consumer logs) usually mean the session timeout is too short or consumers are slow to poll.
3. Raise `session.timeout.ms` to 45 s for slow consumers.

## Broker disk full

When disks fill, brokers stop accepting writes and producers start buffering. Free space by deleting old segments of high-volume topics (`kafka-configs --alter --add-config retention.ms=...`), then expand volumes.

## Consumers

[[F-LINK-30|Warehouse Loader]] and, since August, the [[F-LINK-27|Notification Service]] consume from the cluster; [[F-LINK-18|Order Service]] and [[F-LINK-32|Inventory Service]] produce to it.
