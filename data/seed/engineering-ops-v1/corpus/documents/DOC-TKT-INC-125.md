# INC-125: Mobile app users rate-limited

Severity: SEV3 | Status: Resolved | Primary service: API Gateway
Opened: 2026-08-29 13:20 UTC (impact started 13:02 UTC)
Affected services: edge (primary)

## Description
Many mobile users received "Too many requests" errors.

## Impact
About 14% of mobile requests were rejected with HTTP 429 for an hour, mostly from users on carrier networks sharing IP addresses.

## Detection
429 rate alert at the edge.

## Initial notes from the incident channel
Bot traffic.

## Resolution note
Cause: Rate limit policy v7 (the API Gateway config change rl-policy-v7) keyed limits by client IP. Mobile carriers place thousands of users behind shared NAT addresses, so they shared one bucket.
Reverted to policy v6 (the rollback of API Gateway to rl-policy-v6).
Resolved: 2026-08-29 14:05 UTC
