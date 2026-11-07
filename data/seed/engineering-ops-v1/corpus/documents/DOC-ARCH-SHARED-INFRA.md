# Shared infrastructure overview

_Owner: Platform SRE._

Platform SRE owns the API Gateway, the Orders DB cluster and Shared Redis.

## API Gateway (edge)

Envoy-based edge for web and mobile. Terminates TLS, applies rate limits and routes to the Checkout API and the Catalog Service. Authenticated routes call the Auth Service to validate tokens.

## Orders DB (pg-orders)

PostgreSQL 16 primary with one streaming read replica. Despite the name it is shared: orders, payments and ledger schemas all live here. Clients: Order Service, Payments API, Ledger Service and Warehouse Loader (replica only). max_connections is 600.

## Shared Redis (cache cluster)

Redis 7 with separate shards for sessions, carts and general caches. Users: Auth Service sessions, Cart Service carts and Catalog Service cache. Persistence is disabled by default because most data is cache.
