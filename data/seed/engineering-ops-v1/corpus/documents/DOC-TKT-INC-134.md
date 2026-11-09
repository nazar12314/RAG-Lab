# INC-134: Cart and checkout totals disagree by one cent

Severity: SEV3 | Status: Resolved | Primary service: Pricing Engine
Opened: 2026-10-15 15:00 UTC (impact started 10:10 UTC)
Affected services: pricing-service (primary), Cart Service (downstream), checkout service (downstream)

## Description
Some carts showed a total one cent different from the checkout total, and a few payments were rejected for amount mismatch.

## Impact
About 0.4% of checkouts were blocked by an amount mismatch error for 26 hours.

## Detection
Support reports of "total changed" errors.

## Initial notes from the incident channel
Currency conversion rates outdated.

## Resolution note
Cause: pricing-service release 2.7.0 moved rounding to line level using half-up rounding while the Cart Service used banker's rounding, producing one-cent differences.
version 2.7.1 of pricing aligned rounding with the Cart Service.
Resolved: 2026-10-16 12:00 UTC
