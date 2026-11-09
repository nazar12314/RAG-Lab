# INC-119: Slow logins and token validation timeouts

Severity: SEV3 | Status: Resolved | Primary service: Auth Service
Opened: 2026-07-24 07:45 UTC (impact started 07:30 UTC)
Affected services: auth-service (primary), Checkout API (downstream), API Gateway (downstream)

## Description
Login and every authenticated request became slow during the morning peak.

## Impact
p95 latency of authenticated requests rose from 180 ms to 2.4 s for two hours; about 1.5% of requests timed out.

## Detection
Latency SLO alert on the gateway.

## Initial notes from the incident channel
Redis latency on session shards.

## Resolution note
Cause: auth v6.2.0 fetched the JWKS key set from the identity provider on every token validation instead of caching it. This was fine at night but overloaded the key endpoint at morning peak.
Rolled back to v6.1.4 (the rollback of Auth Service to v6.1.4); a cached implementation shipped later as v6.2.1.
Resolved: 2026-07-24 10:00 UTC
