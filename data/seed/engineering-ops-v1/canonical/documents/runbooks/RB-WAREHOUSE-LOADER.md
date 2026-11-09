---
id: DOC-RB-WAREHOUSE-LOADER
title: "Runbook: Warehouse Loader (nightly ETL)"
doc_type: runbook
created_at: "2026-05-21T10:00:00Z"
author: Ravi Menon
services: [warehouse-loader, orders-db, event-bus]
---
# Runbook: Warehouse Loader (dw loader)

Owner: Data Platform Team. Not to be confused with Warehouse Sync (physical warehouse stock, Inventory Team).

## Failed nightly load

1. Open the Airflow DAG `orders_daily` and read the failing task log.
2. `column ... does not exist` means an upstream schema change; update the column mapping.
3. Backfill with `airflow dags backfill orders_daily -s <date> -e <date>`.

## Export source

[[F-LINK-31|The nightly export reads from the Orders DB]] - always through the replica endpoint `pg-orders-replica`. After any replica rebuild, verify the connection string; pointing at the primary can saturate the production database.

## Streaming tables

[[F-LINK-30|Near-real-time tables are fed from the Event Bus.]] If counts look inflated, check the producing service for duplicate events before blaming the loader.
