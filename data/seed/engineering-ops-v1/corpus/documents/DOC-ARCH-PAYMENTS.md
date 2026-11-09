# Payments platform architecture

_Updated 20 July 2026 after fraud scoring moved into the payment flow. Owner: Payments Team._

## Components

| Component | Role |
| --- | --- |
| Payments API (pay-api) | Public payment entry point used by checkout |
| Fraud Scoring Service | ML risk score per transaction |
| PSP Adapter | Talks to the PayNova card processor |
| Ledger Service | Double-entry bookkeeping |

The Payments API is owned by the Payments Team, as is the PSP Adapter.

## Authorization path

Checkout API calls pay-api synchronously to authorize a card payment. Since 1 June 2026, the Payments API calls the Fraud Scoring Service before every authorization; before that date checkout called fraud scoring itself. pay-api then forwards the authorization to the PSP Adapter, which calls the PayNova API. PayNova is currently our only card processor.

## Persistence

Payment records live in the payments schema of the shared Orders DB (pg-orders). Each pay-api pod keeps its own connection pool to pg-orders; pool sizing matters because the database is shared with the Order Service and the Ledger Service.

Captures and refunds are sent to the Ledger Service asynchronously through a queue, so a slow ledger does not block checkout. The ledger also stores its entries in the Orders DB.

## Known risks

- Single card processor; no failover.
- Shared database: a heavy query from any of the three payment-adjacent services can starve the others.
- The legacy hostname payment-service was removed in v3.0.0, but older runbooks and dashboards still use it.
