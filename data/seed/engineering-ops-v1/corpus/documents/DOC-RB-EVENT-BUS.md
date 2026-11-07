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

Warehouse Loader and, since August, the Notification Service consume from the cluster; Order Service and Inventory Service produce to it.
