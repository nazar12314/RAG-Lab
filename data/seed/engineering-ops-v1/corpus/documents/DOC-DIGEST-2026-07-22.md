# Ops review - 22 July 2026 to 4 August 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-119** (SEV3, Auth Service) - Login and every authenticated request became slow during the morning peak.
  Cause: Auth Service release 6.2.0 fetched the JWKS key set from the identity provider on every token validation instead of caching it. This was fine at night but overloaded the key endpoint at morning peak.
- **INC-120** (SEV3, Orders DB) - Customers saw outdated order statuses because the read replica fell behind.
  Cause: An aggressive manual VACUUM FULL on a large audit table on the Orders DB primary generated a burst of WAL that the replica could not apply fast enough.

## Deployments
4 production deployments this period, including 1 rollback.
- auth-service v6.2.0 was rolled back to v6.1.4 on 24 July 2026.

## Notes
- On-call handovers happened on time for all rotations.
- Reminder: the Friday afternoon change freeze applies to all tier 1 services.
