---
id: DOC-RB-ORDERS-DB
title: "Runbook: Orders DB (pg-orders)"
doc_type: runbook
created_at: "2026-05-22T09:00:00Z"
author: Hannah Becker
services: [orders-db, order-service, payments-api, ledger-service, warehouse-loader]
---
# Runbook: Orders DB (pg-orders)

Owner: Platform SRE. The cluster is shared by orders, payments and ledger, so a problem here usually looks like a checkout or payments outage first.

## Alerts

- **OrdersDbActiveConnectionsHigh** - more than 480 of 600 connections in use.
- **OrdersDbCpuHigh** - primary CPU above 85% for 5 minutes.
- **ReplicaLagHigh** - replica more than 60 s behind.

## Database saturation

Signs: CPU or I/O pegged, many sessions in `active` state, clients reporting "too many connections" or connection checkout timeouts.

1. Find the heaviest sessions:
   `SELECT pid, usename, application_name, state, now() - query_start AS age, left(query, 80) FROM pg_stat_activity ORDER BY age DESC LIMIT 20;`
2. Check `application_name`. Analytics jobs must never run on the primary - [[F-LINK-31|the Warehouse Loader is only allowed to read from the replica.]]
3. Cancel the offending query with `pg_cancel_backend(pid)`; terminate only if cancel fails.
4. Look for new queries without indexes (sequential scans on payments or orders tables) - recent releases of any of the three client services are suspects.

## Replica lag

Avoid VACUUM FULL or large index builds on the primary during business hours; they generate WAL bursts the replica cannot keep up with.

## Clients

[[F-LINK-17|Order Service]], [[F-LINK-14|Payments API]] and [[F-LINK-16|Ledger Service]] write to the primary.
