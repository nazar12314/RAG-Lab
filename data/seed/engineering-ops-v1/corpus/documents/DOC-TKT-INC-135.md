# INC-135: Event bus brokers out of disk

Severity: SEV2 | Status: Resolved | Primary service: Event Bus
Opened: 2026-10-20 11:34 UTC (impact started 11:30 UTC)
Affected services: Event Bus (primary), Notification Service (downstream), Warehouse Loader (downstream), Order Service (degraded), Inventory Service (degraded)

## Description
Order and stock events stopped flowing when Kafka brokers ran out of disk, delaying notifications.

## Impact
For about 100 minutes order notifications were not sent and stock events were not published; producers buffered and retried, so no events were lost.

## Detection
BrokerDiskUsage alert.

## Initial notes from the incident channel
Duplicate stock events filling disks again.

## Resolution note
Retention on high-volume topics was cut to 48 hours and broker volumes were expanded (the event-bus config change retention-48h).
Full analysis in the postmortem DOC-PM-INC-135.
Resolved: 2026-10-20 15:00 UTC
