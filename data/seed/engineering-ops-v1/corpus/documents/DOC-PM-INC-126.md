# Postmortem: INC-126 - Slow checkout during Redis maintenance

Date: 3 September 2026 | Authors: Checkout Team | Status: Final

## Summary
Checkout became very slow early in the morning while Redis was being patched.
INC-126 was a SEV2 incident with Checkout API as the primary service. Impact started at 05:10 UTC on 3 September 2026, was mitigated at 06:30 UTC and the incident was resolved at 07:15 UTC on 3 September 2026 (total 2 h 5 min).

## Customer impact
For about 80 minutes the median checkout step took 6 seconds instead of 400 ms; conversion in Asia-Pacific markets dropped by a third.
Affected services: Checkout API (primary), Pricing Engine (degraded), Catalog Service (degraded), Shared Redis (degraded), Cart Service (degraded)

## Timeline (UTC)
- 05:00 - Redis rolling restart begins.
- 05:20 - Latency alert.
- 06:30 - Cache warmed.

## Root cause
The rolling restart during the shared-redis redis-7.2.5 upgrade emptied the catalog cache in Shared Redis. Every price calculation in the Pricing Engine then needed fresh product data from the Catalog Service, which could not keep up with the cache-miss storm, slowing the whole checkout chain.
Trigger: the Shared Redis redis-7.2.5 upgrade.

## Resolution
Catalog cache was pre-warmed from a snapshot and request coalescing was enabled in the Catalog Service.

## Action items
- [ ] Warm caches before returning a restarted shard to service
- [ ] Schedule Redis maintenance outside APAC peak
