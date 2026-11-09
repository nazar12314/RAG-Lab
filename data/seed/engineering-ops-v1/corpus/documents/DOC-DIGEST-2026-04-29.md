# Ops review - 29 April 2026 to 12 May 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-106** (SEV2, Inventory Service) - Customers were able to buy items that were already out of stock.
  Postmortem pending. Working theory: Reservation expiry bug in inventory.
- **INC-107** (SEV3, pricing-service) - Category discounts stacked on top of each other, giving some customers up to 60% off.
  Cause: Rule set r42 (the pricing config change v2.6.0+rules-r42) marked two overlapping category promotions as stackable, so the Pricing Engine applied both.

## Deployments
7 production deployments this period, including 2 rollbacks.
- warehouse-sync v2.0.0 was rolled back to v1.9.4 on 4 May 2026.
- Pricing Engine v2.6.0+rules-r42 was rolled back to v2.6.0+rules-r41 on 11 May 2026.

## Notes
- The status page template was updated with clearer wording.
- Runbook review: please confirm the owner field on your team's runbooks.
