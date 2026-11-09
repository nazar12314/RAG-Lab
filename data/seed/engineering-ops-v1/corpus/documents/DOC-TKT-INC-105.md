# INC-105: Nightly data warehouse load failed

Severity: SEV4 | Status: Resolved | Primary service: Warehouse Loader
Opened: 2026-04-28 06:30 UTC (impact started 02:00 UTC)
Affected services: nightly ETL (primary)

## Description
The nightly ETL into the analytics warehouse failed and dashboards showed no orders for April 27.

## Impact
Finance and analytics dashboards were a day stale. No customer impact.

## Detection
Data Platform morning check found the orders_daily table empty for the previous day.

## Initial notes from the incident channel
Possibly a permissions problem on the orders-db read replica.

## Resolution note
Cause: The schema migration in the Order Service v4.2.0 release renamed the column shipping_addr to shipping_address. The warehouse-loader export query still selected the old column name and failed every night.
warehouse-loader release 1.3.1 updated the column mapping and the missing day was backfilled.
Resolved: 2026-04-29 12:00 UTC
