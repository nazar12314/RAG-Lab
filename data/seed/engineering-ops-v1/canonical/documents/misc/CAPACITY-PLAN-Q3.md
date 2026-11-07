---
id: DOC-CAPACITY-PLAN-Q3
title: Q3 2026 capacity plan
doc_type: report
created_at: "2026-06-30T12:00:00Z"
author: Hannah Becker
services: [orders-db, shared-redis, event-bus, api-gateway]
---
# Q3 2026 capacity plan

## Orders DB

Peak connections in Q2 were 410 of 600. Each new client service must justify its pool size. We will add a second read replica in Q4.

## Shared Redis

Session shards were doubled to 16 GB after the April session loss. Cart shard usage is 60%.

## Event Bus

Current broker disks are 1 TB each, 55% full with seven-day retention. Notifications and inventory are joining the cluster in August, which may double write volume. **Action:** revisit disk size or retention after the migration. Owner: Data Platform. No date agreed yet.

## Edge

The gateway handles 18k requests per second at peak, 35% of tested capacity.
