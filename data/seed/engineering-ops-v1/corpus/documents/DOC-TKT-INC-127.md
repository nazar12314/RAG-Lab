# INC-127: Fraud model false positives decline good customers

Severity: SEV3 | Status: Resolved | Primary service: Fraud Scoring Service
Opened: 2026-09-09 13:00 UTC (impact started 09:10 UTC)
Affected services: Fraud Scoring Service (primary), payments-api (downstream)

## Description
Fraud declines tripled after the new fraud model went live.

## Impact
About 1.8% of payments were wrongly declined as fraudulent for seven hours.

## Detection
Fraud decline rate dashboard reviewed by the Payments team.

## Initial notes from the incident channel
Model v24 is over-sensitive.

## Resolution note
Cause: fraud-service release 2.4.0 combined a new model with a lower decline threshold (0.85 instead of 0.92); the combination flagged many legitimate first-time customers.
Rolled back to v2.3.2 (the rollback of Fraud Scoring Service to v2.3.2); the model was re-released later with the old threshold.
Resolved: 2026-09-09 16:30 UTC
