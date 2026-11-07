# Postmortem: INC-123 - Payments outage caused by orders database overload

Date: 17 August 2026 | Authors: Payments Team | Status: Final

## Summary
Payments failed and orders could not be placed while the orders database was pegged at 100% CPU.
INC-123 was a SEV1 incident with Payments API as the primary service. Impact started at 09:00 UTC on 17 August 2026, was mitigated at 10:15 UTC and the incident was resolved at 12:40 UTC on 17 August 2026 (total 3 h 40 min).

## Customer impact
For 75 minutes about 60% of checkouts failed, the largest outage of the quarter. Ledger postings were delayed but none were lost.
Affected services: Payments API (primary), primary postgres (degraded), payments ledger (degraded), Order Service (degraded), Checkout API (downstream)

## Timeline (UTC)
- 07:30 - version 5.6.0 of Checkout API deployed.
- 08:10 - version 3.1.0 of payments-api deployed.
- 09:00 - Finance dashboard begins polling the reconciliation endpoint.
- 09:04 - Database CPU and payment latency alerts; SEV1 declared.
- 09:40 - Top query traced to the reconciliation endpoint.
- 10:10 - recon_v2 flag disabled; CPU drops.
- 12:40 - Index added via hotfix.

## Root cause
The new settlement reconciliation endpoint in Payments API v3.1.0 ran a refund listing query without a supporting index. When the Finance dashboard started polling it at 09:00, each call scanned the full payments table on the Orders DB primary. CPU saturation slowed every query; payments, ledger and order-service connection pools were depleted and requests timed out.
Trigger: the Payments API v3.1.0 release.

## Ruled out
Checkout API release 5.6.0 was examined first because it shipped the same morning, but its traffic pattern was unchanged and its error rate followed the database, not the other way round. It was ruled out.

## Resolution
The recon_v2 feature flag was turned off at 10:10, which stopped the expensive query, and version 3.1.1 of payments backend added the missing index at 12:40. No rollback was needed.

## Action items
- [ ] Query plan review for new endpoints on the shared database
- [ ] Per-service statement timeouts on orders-db
- [ ] Rate limit for internal dashboard polling
