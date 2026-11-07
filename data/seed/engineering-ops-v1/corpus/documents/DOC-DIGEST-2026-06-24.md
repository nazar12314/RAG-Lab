# Ops review - 24 June 2026 to 7 July 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-114** (SEV3, Cart Service) - Customers found their shopping carts empty.
  Cause: A hardware failure triggered a failover of the cart shard in session cache. Persistence was disabled, so the promoted replica started with an incomplete dataset after a full resync.
- **INC-115** (SEV2, Checkout API) - Returning customers with a saved address got a server error on the shipping step.
  Postmortem pending. Working theory: Accounts Service returning malformed addresses.

## Deployments
6 production deployments this period, including 1 rollback.
- Checkout API v5.4.0 was rolled back to v5.3.2 on 2 July 2026.

## Notes
- Synthetic checkout probes were extended to the mobile API.
- Two new engineers joined the payments-primary rotation.
