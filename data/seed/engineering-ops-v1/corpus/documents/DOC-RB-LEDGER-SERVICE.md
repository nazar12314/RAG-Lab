# Runbook: Ledger Service

Owner: Payments Team (finance engineering rotation).

## Reconciliation mismatch

The nightly job compares the PayNova settlement file with ledger entries. A mismatch on refunds usually means double posting:

1. Query postings grouped by refund id with more than one row.
2. Check whether the idempotency key format changed recently.
3. Do not delete postings; Finance corrects them with reversal entries.

## Delayed postings

Payments API sends captures and refunds through a queue, so the ledger can fall behind without affecting checkout. The ledger writes to the Orders DB; if the database is saturated, postings queue up and are processed once it recovers.
