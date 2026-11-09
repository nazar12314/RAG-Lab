# INC-133: Checkout outage after new checkout release

Severity: SEV1 | Status: Resolved | Primary service: Checkout API
Opened: 2026-10-12 08:24 UTC (impact started 08:20 UTC)
Affected services: Checkout API (primary), Inventory Service (degraded), Order Service (downstream)

## Description
Most customers could not get through checkout after the new single-page checkout launched.

## Impact
For 95 minutes about 70% of checkout attempts failed or timed out. Orders that did go through were correct.

## Detection
CheckoutSuccessRate alert at 08:24.

## Initial notes from the incident channel
The Inventory Service is down.

## Resolution note
The release was rolled back to v5.7.1 at 09:10 (the rollback of Checkout API to v5.7.1). The rollback alone was only partially effective; inventory pods remained saturated with queued requests until they were restarted at 09:50, after which checkout success returned to normal at 09:55.
Full analysis in the postmortem DOC-PM-INC-133.
Resolved: 2026-10-12 10:30 UTC
