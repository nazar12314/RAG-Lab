---
id: DOC-RB-LEDGER-SERVICE
title: "Runbook: Ledger Service"
doc_type: runbook
created_at: "2026-07-22T10:00:00Z"
author: Marta Kowalczyk
services: [ledger-service, payments-api, orders-db]
---
# Runbook: Ledger Service

[[F-OWNER-ledger-service|Owner: Payments Team (finance engineering rotation).]]

## Reconciliation mismatch

The nightly job compares the PayNova settlement file with ledger entries. A mismatch on refunds usually means double posting:

1. Query postings grouped by refund id with more than one row.
2. Check whether the idempotency key format changed recently.
3. Do not delete postings; Finance corrects them with reversal entries.

## Delayed postings

[[F-LINK-13|Payments API sends captures and refunds through a queue]], so the ledger can fall behind without affecting checkout. [[F-LINK-16|The ledger writes to the Orders DB]]; if the database is saturated, postings queue up and are processed once it recovers.
