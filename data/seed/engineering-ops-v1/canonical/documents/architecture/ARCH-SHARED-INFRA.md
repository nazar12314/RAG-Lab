---
id: DOC-ARCH-SHARED-INFRA
title: Shared infrastructure overview
doc_type: architecture
created_at: "2026-04-02T08:00:00Z"
author: Hannah Becker
services: [api-gateway, orders-db, shared-redis]
---
# Shared infrastructure overview

_Owner: Platform SRE._

[[F-OWNER-api-gateway|Platform SRE owns the API Gateway]], [[F-OWNER-orders-db|the Orders DB cluster]] [[F-OWNER-shared-redis|and Shared Redis]].

## API Gateway (edge)

Envoy-based edge for web and mobile. Terminates TLS, applies rate limits and routes to [[F-LINK-02|the Checkout API]] and [[F-LINK-03|the Catalog Service]]. [[F-LINK-01|Authenticated routes call the Auth Service to validate tokens.]]

## Orders DB (pg-orders)

PostgreSQL 16 primary with one streaming read replica. Despite the name it is shared: orders, payments and ledger schemas all live here. Clients: [[F-LINK-17|Order Service]], [[F-LINK-14|Payments API]], [[F-LINK-16|Ledger Service]] and [[F-LINK-31|Warehouse Loader (replica only)]]. max_connections is 600.

## Shared Redis (cache cluster)

Redis 7 with separate shards for sessions, carts and general caches. Users: [[F-LINK-22|Auth Service sessions]], [[F-LINK-19|Cart Service carts]] and [[F-LINK-25|Catalog Service cache]]. Persistence is disabled by default because most data is cache.
