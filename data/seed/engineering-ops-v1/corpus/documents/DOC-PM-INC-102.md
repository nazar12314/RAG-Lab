# Postmortem: INC-102 - Users logged out and unable to sign in

Date: 9 April 2026 | Authors: Identity Team | Status: Final

## Summary
Customers were randomly signed out, including in the middle of checkout, and some could not log back in.
INC-102 was a SEV2 incident with Auth Service as the primary service. Impact started at 13:05 UTC on 9 April 2026, was mitigated at 15:20 UTC and the incident was resolved at 16:45 UTC on 9 April 2026 (total 3 h 40 min).

## Customer impact
For about two hours roughly one in five active sessions was dropped. Customers lost their place in checkout and had to log in again; around 9% of login attempts failed with a generic error.
Affected services: Auth Service (primary), Shared Redis (degraded), checkout service (downstream), API Gateway (downstream)

## Timeline (UTC)
- 13:12 - AuthSessionMissRateHigh alert fires.
- 13:40 - Identity on-call sees sessions missing from Shared Redis.
- 14:30 - evicted_keys counter found climbing on all shards.
- 15:20 - Eviction policy and memory limit changed; errors drop.
- 16:45 - Incident resolved after an hour of stable metrics.

## Root cause
The shared-redis shards were at their 8 GB memory limit and the allkeys-lru eviction policy started evicting live session keys, which have no TTL priority over cache entries. Traffic growth after the spring campaign pushed memory over the limit.
No deployment triggered this incident.

## Ruled out
The session key prefix change shipped in auth-service v6.0.0 was reviewed and is unrelated; keys were present until evicted.

## Resolution
Platform SRE switched the eviction policy to volatile-lru and doubled maxmemory to 16 GB per shard (the Shared Redis config change maxmemory-policy-volatile-lru); session loss stopped immediately after the change.

## Action items
- [ ] Separate the session cache from general caches
- [ ] Alert on Redis evicted_keys rate
