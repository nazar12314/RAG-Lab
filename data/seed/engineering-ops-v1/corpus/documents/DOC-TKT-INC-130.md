# INC-130: Order cancellations stuck in pending

Severity: SEV3 | Status: Resolved | Primary service: OMS
Opened: 2026-09-27 08:30 UTC (impact started 17:10 UTC)
Affected services: Order Service (primary), Payments API (downstream)

## Description
Customer-requested cancellations stayed in "cancellation pending" and refunds were not triggered.

## Impact
870 cancellations were stuck overnight; refunds were delayed by up to 18 hours.

## Detection
Support escalation.

## Initial notes from the incident channel
Payments refund API failing.

## Resolution note
Cause: The rewritten transition table in order-service v4.5.0 was missing the transition from cancellation_pending to cancelled when the order had been partially shipped.
Rolled back to v4.4.0 (the rollback of order-service to v4.4.0) and stuck orders were reprocessed.
Resolved: 2026-09-27 12:00 UTC
