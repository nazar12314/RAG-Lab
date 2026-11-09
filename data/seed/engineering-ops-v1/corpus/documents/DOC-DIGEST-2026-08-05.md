# Ops review - 5 August 2026 to 18 August 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-122** (SEV4, inventory-service) - Analytics showed stock movements roughly doubled since early August.
  Cause: The producer introduced in the Inventory Service v3.6.0 release retried on timeouts without idempotence, publishing many stock-changed events twice.
- **INC-121** (SEV2, Notification Service) - No order confirmation or shipping emails were sent for more than three hours.
  Postmortem pending. Working theory: Order Service webhook disabled too early.
- **INC-123** (SEV1, Payments API) - Payments failed and orders could not be placed while the orders database was pegged at 100% CPU.
  Postmortem pending. Working theory: The checkout-api v5.6.0 express checkout release at 07:30 could be increasing load on payments.

## Deployments
7 production deployments this period, including 0 rollbacks.

## Notes
- Reminder: the Friday afternoon change freeze applies to all tier 1 services.
- Alert noise review: 14 alerts were tuned or deleted.
