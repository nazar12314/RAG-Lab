---
id: DOC-RB-SHARED-REDIS
title: "Runbook: Shared Redis"
doc_type: runbook
created_at: "2026-07-01T10:00:00Z"
author: Hannah Becker
services: [shared-redis, auth-service, cart-service, catalog-service]
---
# Runbook: Shared Redis (cache cluster)

Owner: Platform SRE.

## Shards

| Shard group | Used by | Persistence |
| --- | --- | --- |
| sessions | Auth Service | AOF since June |
| carts | Cart Service | AOF since June |
| cache | Catalog Service, misc | none |

## Memory pressure

Watch `used_memory` against `maxmemory` and the `evicted_keys` counter. The eviction policy is volatile-lru so keys without a TTL are never evicted; if memory still fills, scale the shard rather than changing the policy.

## Failover

A failover of the sessions shard logs users out if persistence is off. After any failover check key counts against the previous day.

## Maintenance

Rolling restarts empty the cache shards. Warm the catalog cache before returning a shard to service and avoid restarts between 05:00 and 09:00 UTC (APAC peak).
