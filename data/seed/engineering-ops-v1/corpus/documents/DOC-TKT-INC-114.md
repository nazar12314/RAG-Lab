# INC-114: Shopping carts emptied after Redis failover

Severity: SEV3 | Status: Resolved | Primary service: cart-service
Opened: 2026-06-26 21:25 UTC (impact started 21:10 UTC)
Affected services: Cart Service (primary), Shared Redis (primary)

## Description
Customers found their shopping carts empty.

## Impact
Roughly 180,000 stored carts were lost. Customers had to re-add items; no orders were affected.

## Detection
Spike in "my cart is empty" contacts.

## Initial notes from the incident channel
Cart TTL change from April expiring carts early.

## Resolution note
Cause: A hardware failure triggered a failover of the cart shard in shared-redis. Persistence was disabled, so the promoted replica started with an incomplete dataset after a full resync.
AOF persistence was enabled on cart and session shards (the shared-redis config change appendonly-yes); the Cart Service later added a database fallback.
Resolved: 2026-06-27 09:00 UTC
