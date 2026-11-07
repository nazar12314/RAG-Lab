# Ops review - 15 April 2026 to 28 April 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-103** (SEV3, Email Dispatcher) - Order confirmation and shipping emails arrived up to four hours late.
  Cause: MailRelay started returning HTTP 429 after our sending volume exceeded the account's hourly quota during a flash sale. The email-dispatcher retried with a fixed one-minute delay, which kept us above the quota.
- **INC-104** (SEV1, Payments API) - Customers could not complete purchases because payment requests timed out on the final checkout step.
  Postmortem pending. Working theory: The cart-service v1.12.0 release (cart merge on login) went out at 09:40, shortly before errors began, and is the main suspect.
- **INC-105** (SEV4, Warehouse Loader) - The nightly ETL into the analytics warehouse failed and dashboards showed no orders for April 27.
  Cause: The schema migration in order management release 4.2.0 renamed the column shipping_addr to shipping_address. The warehouse-loader export query still selected the old column name and failed every night.

## Deployments
6 production deployments this period, including 1 rollback.
- pay-api v2.8.0 was rolled back to v2.7.3 on 22 April 2026.

## Notes
- Reminder: the Friday afternoon change freeze applies to all tier 1 services.
- Alert noise review: 14 alerts were tuned or deleted.
