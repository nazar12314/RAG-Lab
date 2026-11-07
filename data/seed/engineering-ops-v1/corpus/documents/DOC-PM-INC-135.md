# Postmortem: INC-135 - Event bus brokers out of disk

Date: 20 October 2026 | Authors: Data Platform Team | Status: Final

## Summary
Order and stock events stopped flowing when Kafka brokers ran out of disk, delaying notifications.
INC-135 was a SEV2 incident with Event Bus as the primary service. Impact started at 11:30 UTC on 20 October 2026, was mitigated at 13:10 UTC and the incident was resolved at 15:00 UTC on 20 October 2026 (total 3 h 30 min).

## Customer impact
For about 100 minutes order notifications were not sent and stock events were not published; producers buffered and retried, so no events were lost.
Affected services: Event Bus (primary), notification-service (downstream), Warehouse Loader (downstream), orders (degraded), Inventory Service (degraded)

## Timeline (UTC)
- 11:34 - Disk alert.
- 13:10 - Old segments deleted; writes resume.
- 15:00 - Retention change and volume expansion completed.

## Root cause
Event volume roughly doubled after the event bus migration, but topic retention stayed at seven days and broker disks were never resized. Disks filled and brokers stopped accepting writes.
No deployment triggered this incident.

## Resolution
Retention on high-volume topics was cut to 48 hours and broker volumes were expanded (the event-bus config change retention-48h).

## Action items
- [ ] Capacity review after migrations
- [ ] Disk alert at 70%
