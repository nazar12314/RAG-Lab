# INC-129: Login outage after signing key expiry

Severity: SEV2 | Status: Resolved | Primary service: auth
Opened: 2026-09-21 00:04 UTC (impact started 00:00 UTC)
Affected services: auth-service (primary), api-gateway (downstream), co-api (downstream), Accounts Service (downstream)

## Description
Nobody could log in for 25 minutes and existing sessions were rejected.

## Impact
All authenticated traffic failed for 25 minutes around midnight UTC.

## Detection
Auth error rate alert.

## Initial notes from the incident channel
JWKS caching from v6.2.1.

## Resolution note
An emergency key rotation was performed by the Identity on-call.
Full analysis in the postmortem DOC-PM-INC-129.
Resolved: 2026-09-21 01:00 UTC
