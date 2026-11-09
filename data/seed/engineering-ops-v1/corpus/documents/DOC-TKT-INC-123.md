# INC-123: Payments outage caused by orders database overload

Severity: SEV1 | Status: Resolved | Primary service: payments-api
Opened: 2026-08-17 09:04 UTC (impact started 09:00 UTC)
Affected services: payments-api (primary), orders-db (degraded), Ledger Service (degraded), Order Service (degraded), Checkout API (downstream)

## Description
Payments failed and orders could not be placed while the orders database was pegged at 100% CPU.

## Impact
For 75 minutes about 60% of checkouts failed, the largest outage of the quarter. Ledger postings were delayed but none were lost.

## Detection
OrdersDbCpuHigh and PaymentAuthLatency alerts fired within a minute of each other at 09:04.

## Initial notes from the incident channel
The checkout-api v5.6.0 express checkout release at 07:30 could be increasing load on payments.

## Resolution note
The recon_v2 feature flag was turned off at 10:10, which stopped the expensive query, and Payments API release 3.1.1 added the missing index at 12:40. No rollback was needed.
Full analysis in the postmortem DOC-PM-INC-123.
Resolved: 2026-08-17 12:40 UTC
