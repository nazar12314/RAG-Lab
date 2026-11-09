# Shared Infrastructure release notes - April 2026

Production changes shipped by Shared Infrastructure services in April 2026.

### Config: Shared Redis maxmemory-policy-volatile-lru
Deployed 2026-04-09 15:20 UTC by Hannah Becker.
- Changed eviction policy from allkeys-lru to volatile-lru
- Increased maxmemory from 8 GB to 16 GB per shard

