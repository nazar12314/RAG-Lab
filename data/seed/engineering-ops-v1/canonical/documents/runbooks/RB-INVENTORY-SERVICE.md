---
id: DOC-RB-INVENTORY-SERVICE
title: "Runbook: Inventory Service"
doc_type: runbook
created_at: "2026-05-06T10:00:00Z"
author: Jonas Lindqvist
services: [inventory-service, warehouse-sync, checkout-api]
---
# Runbook: Inventory Service (stock service)

Owner: Inventory Team.

## Alerts

- **InventoryThreadPoolSaturation** - request worker pool more than 90% busy.
- **StockFreshness** - no stock update from the partner WMS for 60 minutes.
- **OversellDetector** - orders accepted for SKUs with zero stock.

## Thread pool saturation

The service has a fixed worker pool of 200 threads. When callers send many more stock checks than usual, requests queue and time out. Queued requests are not shed automatically, so after the excess traffic stops the pods may stay saturated; restart pods one zone at a time to clear the queue.

## Overselling

[[F-LINK-24|Stock updates come from Warehouse Sync.]] If the oversell detector fires, pause Warehouse Sync first (`deployctl scale warehouse-sync --replicas 0`), then compare stock with the WMS export and run the reconciliation script.

## Stale stock

Check the Warehouse Sync logs for 401 or 429 errors from the partner WMS.
