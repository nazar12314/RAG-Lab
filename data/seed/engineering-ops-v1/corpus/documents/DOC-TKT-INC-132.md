# INC-132: Notification service restarting repeatedly

Severity: SEV3 | Status: Resolved | Primary service: notifications
Opened: 2026-10-06 14:30 UTC (impact started 14:00 UTC)
Affected services: Notification Service (primary)

## Description
Notification pods were repeatedly killed for running out of memory, delaying emails by minutes.

## Impact
Notifications were delayed by up to 20 minutes during restarts; none were lost.

## Detection
Pod restart alert.

## Initial notes from the incident channel
Memory leak in the event bus client.

## Resolution note
Cause: The in-memory template cache added in version 4.2.0 of notifications was unbounded and grew with every personalised template variant until pods hit their memory limit.
notification-service v4.2.1 bounded the cache with LRU eviction.
Resolved: 2026-10-07 16:00 UTC
