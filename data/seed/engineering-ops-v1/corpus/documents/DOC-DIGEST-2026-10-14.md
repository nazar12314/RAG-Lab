# Ops review - 14 October 2026 to 27 October 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-134** (SEV3, Pricing Engine) - Some carts showed a total one cent different from the checkout total, and a few payments were rejected for amount mismatch.
  Cause: version 2.7.0 of pricing-service moved rounding to line level using half-up rounding while the Cart Service used banker's rounding, producing one-cent differences.
- **INC-135** (SEV2, event-bus) - Order and stock events stopped flowing when Kafka brokers ran out of disk, delaying notifications.
  Postmortem pending. Working theory: Duplicate stock events filling disks again.
- **INC-136** (SEV4, Catalog Service) - Some product pages showed "in stock" badges for sold-out items.
  Cause: The root cause was not determined. Stock events were verified to be correct, and the problem disappeared after the cache was flushed.

## Deployments
3 production deployments this period, including 0 rollbacks.

## Notes
- Synthetic checkout probes were extended to the mobile API.
- Two new engineers joined the payments-primary rotation.
