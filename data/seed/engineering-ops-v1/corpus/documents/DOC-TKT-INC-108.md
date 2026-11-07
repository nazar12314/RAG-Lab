# INC-108: Orders database saturation slows checkout and payments

Severity: SEV2 | Status: Resolved | Primary service: Orders DB
Opened: 2026-05-19 13:58 UTC (impact started 13:50 UTC)
Affected services: orders-db (primary), order-service (degraded), payments-api (degraded), ledger-service (degraded), Checkout API (downstream)

## Description
Checkout and payment requests became very slow and some failed while the orders database was overloaded.

## Impact
For 50 minutes p99 checkout latency exceeded 12 seconds and about 7% of payments failed with timeouts.

## Detection
OrdersDbActiveConnectionsHigh fired at 13:58; Payments saw "too many connections" errors.

## Initial notes from the incident channel
Looks like the payments connection pool problem from April again.

## Resolution note
The export job was killed at 14:35 and the loader was pinned to the replica endpoint (the Warehouse Loader config change v1.3.1+export-source-replica).
Full analysis in the postmortem DOC-PM-INC-108.
Resolved: 2026-05-19 15:30 UTC
