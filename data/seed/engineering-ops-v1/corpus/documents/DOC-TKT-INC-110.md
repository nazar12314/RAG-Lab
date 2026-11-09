# INC-110: Legitimate payments declined after fraud check change

Severity: SEV2 | Status: Resolved | Primary service: Payments API
Opened: 2026-06-01 11:30 UTC (impact started 09:00 UTC)
Affected services: payments-api (primary), fraud-service (degraded), Checkout API (downstream)

## Description
A spike of card declines for genuine customers after fraud scoring moved into the payment flow.

## Impact
Over 28 hours about 3% of legitimate payments were declined, concentrated at peak hours.

## Detection
Customer support reported customers whose cards were declined but worked elsewhere.

## Initial notes from the incident channel
The fraud model may be too aggressive.

## Resolution note
Payments API release 2.9.1 raised the timeout to 800 ms and made low-value orders fail open when no score is available.
Full analysis in the postmortem DOC-PM-INC-110.
Resolved: 2026-06-02 14:00 UTC
