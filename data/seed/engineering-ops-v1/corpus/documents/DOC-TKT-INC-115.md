# INC-115: Checkout errors for customers with saved addresses

Severity: SEV2 | Status: Resolved | Primary service: Checkout API
Opened: 2026-07-01 09:35 UTC (impact started 09:20 UTC)
Affected services: checkout (primary)

## Description
Returning customers with a saved address got a server error on the shipping step.

## Impact
About 11% of checkout sessions hit an HTTP 500 on the shipping step for almost a day.

## Detection
Checkout5xxRate alert.

## Initial notes from the incident channel
Accounts Service returning malformed addresses.

## Resolution note
The release was rolled back to v5.3.2 the next morning (the rollback of checkout-api to v5.3.2) after a forward fix failed review.
Full analysis in the postmortem DOC-PM-INC-115.
Resolved: 2026-07-02 08:30 UTC
