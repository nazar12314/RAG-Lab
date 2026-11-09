# INC-107: Wrong discounts applied to orders

Severity: SEV3 | Status: Resolved | Primary service: price-calc
Opened: 2026-05-11 09:15 UTC (impact started 08:05 UTC)
Affected services: pricing-service (primary), Cart Service (downstream)

## Description
Category discounts stacked on top of each other, giving some customers up to 60% off.

## Impact
About 1,900 orders received larger discounts than intended over two hours.

## Detection
Finance noticed an unusual drop in average order value.

## Initial notes from the incident channel
Promotion rule set r42 published this morning.

## Resolution note
Cause: Rule set r42 (the Pricing Engine config change v2.6.0+rules-r42) marked two overlapping category promotions as stackable, so the Pricing Engine applied both.
The rule set was reverted to r41 (the rollback of pricing-service to v2.6.0+rules-r41).
Resolved: 2026-05-11 10:20 UTC
