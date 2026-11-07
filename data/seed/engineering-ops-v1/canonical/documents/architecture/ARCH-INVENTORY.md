---
id: DOC-ARCH-INVENTORY
title: Inventory and catalog architecture
doc_type: architecture
created_at: "2026-08-08T10:00:00Z"
author: Jonas Lindqvist
services: [inventory-service, catalog-service, warehouse-sync, shared-redis, event-bus]
---
# Inventory and catalog architecture

_Owner: Inventory Team. Updated after the August event bus migration._

[[F-OWNER-inventory-service|The Inventory Service is owned by the Inventory Team]], [[F-OWNER-catalog-service|together with the Catalog Service]] [[F-OWNER-warehouse-sync|and the Warehouse Sync worker]].

Note: "warehouse" in this document means the physical fulfilment warehouse. The analytics data warehouse and its loader belong to Data Platform.

## Stock

The Inventory Service (stock service) is the source of truth for stock levels. [[F-LINK-24|Warehouse Sync pulls stock deltas from the partner WMS and pushes them into the Inventory Service.]] [[F-LINK-07|Checkout reserves stock synchronously]] [[F-LINK-34|and the Order Service confirms reservations when an order is created.]]

Since 5 August 2026 [[F-LINK-32|the Inventory Service also publishes stock-changed events to the Event Bus]].

## Catalog

The Catalog Service holds product data, images and the search index. [[F-LINK-25|It uses Shared Redis as a read-through cache]] and [[F-LINK-35|consumes stock updates from Inventory asynchronously to show availability badges]]. [[F-LINK-03|The catalog is exposed to clients through the API Gateway.]]

## Pitfalls

- A cold catalog cache turns every pricing request into a catalog database read.
- Stock snapshots must never overwrite newer counts.
