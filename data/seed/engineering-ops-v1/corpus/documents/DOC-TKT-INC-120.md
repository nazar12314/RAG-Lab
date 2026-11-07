# INC-120: Order status page showing stale data

Severity: SEV3 | Status: Resolved | Primary service: primary postgres
Opened: 2026-07-30 12:10 UTC (impact started 11:00 UTC)
Affected services: Orders DB (primary), Order Service (degraded), warehouse-loader (downstream)

## Description
Customers saw outdated order statuses because the read replica fell behind.

## Impact
The order tracking page showed statuses up to 40 minutes old for four hours; support handled extra "where is my order" contacts.

## Detection
ReplicaLagHigh alert.

## Initial notes from the incident channel
Network issue between availability zones.

## Resolution note
Cause: An aggressive manual VACUUM FULL on a large audit table on the orders-db primary generated a burst of WAL that the replica could not apply fast enough.
The vacuum was cancelled and rescheduled for a low-traffic window with throttling; replication caught up by 16:30.
Resolved: 2026-07-30 16:30 UTC
