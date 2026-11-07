# Ops review - 30 September 2026 to 13 October 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-131** (SEV2, provider-gateway) - European customers whose bank requires 3-D Secure could not complete card payments.
  Postmortem pending. Working theory: A bank-side 3DS issue.
- **INC-132** (SEV3, notifier) - Notification pods were repeatedly killed for running out of memory, delaying emails by minutes.
  Cause: The in-memory template cache added in the Notification Service v4.2.0 release was unbounded and grew with every personalised template variant until pods hit their memory limit.
- **INC-133** (SEV1, Checkout API) - Most customers could not get through checkout after the new single-page checkout launched.
  Postmortem pending. Working theory: The Inventory Service is down.

## Deployments
8 production deployments this period, including 1 rollback.
- Checkout API v6.0.0 was rolled back to v5.7.1 on 12 October 2026.

## Notes
- Game day planned for the next period; volunteers welcome.
- On-call handovers happened on time for all rotations.
