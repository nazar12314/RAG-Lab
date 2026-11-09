# INC-128: Warehouse stock sync stalled

Severity: SEV4 | Status: Resolved | Primary service: Warehouse Sync
Opened: 2026-09-15 08:15 UTC (impact started 00:00 UTC)
Affected services: Warehouse Sync (primary), Inventory Service (degraded)

## Description
Stock levels from the partner warehouse stopped updating overnight.

## Impact
Stock was up to ten hours stale; 37 orders were accepted for items that had sold out in store.

## Detection
Stock freshness alert.

## Initial notes from the incident channel
Partner WMS outage.

## Resolution note
Cause: The partner WMS rotated its API credentials at midnight as announced in an email that went to an unmonitored mailbox, so every sync request was rejected with 401.
New credentials were installed in the warehouse sync worker secret store.
Resolved: 2026-09-15 10:00 UTC
