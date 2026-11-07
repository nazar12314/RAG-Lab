# Postmortem: INC-108 - Orders database saturation slows checkout and payments

Date: 19 May 2026 | Authors: Platform SRE | Status: Final

## Summary
Checkout and payment requests became very slow and some failed while the orders database was overloaded.
INC-108 was a SEV2 incident with Orders DB as the primary service. Impact started at 13:50 UTC on 19 May 2026, was mitigated at 14:40 UTC and the incident was resolved at 15:30 UTC on 19 May 2026 (total 1 h 40 min).

## Customer impact
For 50 minutes p99 checkout latency exceeded 12 seconds and about 7% of payments failed with timeouts.
Affected services: orders-db (primary), Order Service (degraded), payments (degraded), finance ledger (degraded), checkout (downstream)

## Timeline (UTC)
- 13:50 - Export job starts against the primary.
- 13:58 - Active connections alert.
- 14:20 - pg_stat_activity shows the export holding 300+ connections.
- 14:35 - Export killed.
- 15:30 - Loader pinned to replica.

## Root cause
After the read replica was rebuilt on May 18, the Warehouse Loader export connection string was left pointing at the primary. An ad-hoc full-table export ran against the orders-db primary, saturating CPU and I/O and holding hundreds of connections, which starved order, payment and ledger traffic.
No deployment triggered this incident.

## Ruled out
Payments API pool settings were checked and were correct (40 connections); this was not a repeat of INC-104.

## Resolution
The export job was killed at 14:35 and the loader was pinned to the replica endpoint (the Warehouse Loader config change v1.3.1+export-source-replica).

## Action items
- [ ] Separate database role for analytics with a connection limit
- [ ] Alert when analytics queries hit the primary
