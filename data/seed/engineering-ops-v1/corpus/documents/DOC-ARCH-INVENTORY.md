# Inventory and catalog architecture

_Owner: Inventory Team. Updated after the August event bus migration._

The Inventory Service is owned by the Inventory Team, together with the Catalog Service and the Warehouse Sync worker.

Note: "warehouse" in this document means the physical fulfilment warehouse. The analytics data warehouse and its loader belong to Data Platform.

## Stock

The Inventory Service (stock service) is the source of truth for stock levels. Warehouse Sync pulls stock deltas from the partner WMS and pushes them into the Inventory Service. Checkout reserves stock synchronously and the Order Service confirms reservations when an order is created.

Since 5 August 2026 the Inventory Service also publishes stock-changed events to the Event Bus.

## Catalog

The Catalog Service holds product data, images and the search index. It uses Shared Redis as a read-through cache and consumes stock updates from Inventory asynchronously to show availability badges. The catalog is exposed to clients through the API Gateway.

## Pitfalls

- A cold catalog cache turns every pricing request into a catalog database read.
- Stock snapshots must never overwrite newer counts.
