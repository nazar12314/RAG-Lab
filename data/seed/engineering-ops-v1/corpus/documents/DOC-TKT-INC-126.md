# INC-126: Slow checkout during Redis maintenance

Severity: SEV2 | Status: Resolved | Primary service: Checkout API
Opened: 2026-09-03 05:20 UTC (impact started 05:10 UTC)
Affected services: Checkout API (primary), pricing-service (degraded), catalog api (degraded), shared-redis (degraded), Cart Service (degraded)

## Description
Checkout became very slow early in the morning while Redis was being patched.

## Impact
For about 80 minutes the median checkout step took 6 seconds instead of 400 ms; conversion in Asia-Pacific markets dropped by a third.

## Detection
CheckoutLatencyHigh alert.

## Initial notes from the incident channel
Checkout API garbage collection pauses.

## Resolution note
Catalog cache was pre-warmed from a snapshot and request coalescing was enabled in the Catalog Service.
Full analysis in the postmortem DOC-PM-INC-126.
Resolved: 2026-09-03 07:15 UTC
