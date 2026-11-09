# INC-122: Duplicated stock events inflate analytics

Severity: SEV4 | Status: Resolved | Primary service: Inventory Service
Opened: 2026-08-11 09:00 UTC (impact started 07:00 UTC)
Affected services: Inventory Service (primary), warehouse-loader (downstream)

## Description
Analytics showed stock movements roughly doubled since early August.

## Impact
Inventory analytics were wrong for a week. Actual stock levels were correct.

## Detection
An analyst noticed stock movement counts far above order volume.

## Initial notes from the incident channel
Warehouse loader reading the topic twice.

## Resolution note
Cause: The producer introduced in the Inventory Service v3.6.0 release retried on timeouts without idempotence, publishing many stock-changed events twice.
inventory-service v3.6.1 added deterministic event ids and idempotent producer retries; analytics were rebuilt.
Resolved: 2026-08-12 10:30 UTC
