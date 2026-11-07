# INC-137: Intermittent payment timeouts after HTTP client upgrade

Severity: SEV2 | Status: Resolved | Primary service: Payments API
Opened: 2026-10-28 09:31 UTC (impact started 09:25 UTC)
Affected services: payments backend (primary), psp-adapter (degraded), Checkout API (downstream)

## Description
About one in ten payments timed out for 40 minutes.

## Impact
11% of payment authorizations timed out between 09:25 and 10:05; customers could retry, and about half of them succeeded on retry.

## Detection
PaymentAuthLatency alert at 09:31.

## Initial notes from the incident channel
The fraud-service v2.5.0 release at 08:30 added fields to the score response and may be slowing payments down.

## Resolution note
payments-api was rolled back to v3.3.1 at 10:05 (the rollback of Payments API to v3.3.1) and timeouts stopped immediately.
Full analysis in the postmortem DOC-PM-INC-137.
Resolved: 2026-10-28 10:30 UTC
