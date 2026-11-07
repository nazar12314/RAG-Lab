# INC-102: Users logged out and unable to sign in

Severity: SEV2 | Status: Resolved | Primary service: Auth Service
Opened: 2026-04-09 13:12 UTC (impact started 13:05 UTC)
Affected services: auth-service (primary), Shared Redis (degraded), Checkout API (downstream), api-gateway (downstream)

## Description
Customers were randomly signed out, including in the middle of checkout, and some could not log back in.

## Impact
For about two hours roughly one in five active sessions was dropped. Customers lost their place in checkout and had to log in again; around 9% of login attempts failed with a generic error.

## Detection
Alert AuthSessionMissRateHigh fired at 13:12 and the support queue spiked with "logged out" complaints.

## Initial notes from the incident channel
Suspect the auth-service v6.0.0 session key prefix change from earlier this week.

## Resolution note
Platform SRE switched the eviction policy to volatile-lru and doubled maxmemory to 16 GB per shard (the Shared Redis config change maxmemory-policy-volatile-lru); session loss stopped immediately after the change.
Full analysis in the postmortem DOC-PM-INC-102.
Resolved: 2026-04-09 16:45 UTC
