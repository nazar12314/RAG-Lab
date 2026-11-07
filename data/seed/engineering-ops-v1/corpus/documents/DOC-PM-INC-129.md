# Postmortem: INC-129 - Login outage after signing key expiry

Date: 21 September 2026 | Authors: Identity Team | Status: Final

## Summary
Nobody could log in for 25 minutes and existing sessions were rejected.
INC-129 was a SEV2 incident with Auth Service as the primary service. Impact started at 00:00 UTC on 21 September 2026, was mitigated at 00:25 UTC and the incident was resolved at 01:00 UTC on 21 September 2026 (total 1 h 0 min).

## Customer impact
All authenticated traffic failed for 25 minutes around midnight UTC.
Affected services: Auth Service (primary), API Gateway (downstream), checkout-api (downstream), Accounts Service (downstream)

## Timeline (UTC)
- 00:04 - Alert.
- 00:25 - Key rotated.

## Root cause
The token signing key expired at midnight because the quarterly manual rotation was missed; newly issued and existing tokens failed validation.
No deployment triggered this incident.

## Ruled out
The JWKS caching in auth-service v6.2.1 was not involved; the cache correctly served the expired key.

## Resolution
An emergency key rotation was performed by the Identity on-call.

## Action items
- [ ] Automate signing key rotation
- [ ] Expiry alert 14 days ahead
