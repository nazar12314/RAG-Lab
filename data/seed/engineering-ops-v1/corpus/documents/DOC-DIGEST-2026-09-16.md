# Ops review - 16 September 2026 to 29 September 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-129** (SEV2, auth-service) - Nobody could log in for 25 minutes and existing sessions were rejected.
  Postmortem pending. Working theory: JWKS caching from v6.2.1.
- **INC-130** (SEV3, OMS) - Customer-requested cancellations stayed in "cancellation pending" and refunds were not triggered.
  Cause: The rewritten transition table in Order Service v4.5.0 was missing the transition from cancellation_pending to cancelled when the order had been partially shipped.

## Deployments
4 production deployments this period, including 1 rollback.
- Order Service v4.5.0 was rolled back to v4.4.0 on 27 September 2026.

## Notes
- Alert noise review: 14 alerts were tuned or deleted.
- Game day planned for the next period; volunteers welcome.
