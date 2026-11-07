# Ops review - 10 June 2026 to 23 June 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-112** (SEV3, Accounts Service) - Customers could not change their address or password; the save button returned an error.
  Cause: The accounts-service database volume ran out of disk space because audit log partitions were not being dropped after their 90-day retention.
- **INC-113** (SEV1, payment provider adapter) - All card payments failed for 47 minutes because the external card processor was down.
  Postmortem pending. Working theory: The psp-adapter v1.6.0 release this morning added support for a new PayNova API version and is the prime suspect.

## Deployments
3 production deployments this period, including 0 rollbacks.

## Notes
- Game day planned for the next period; volunteers welcome.
- On-call handovers happened on time for all rotations.
