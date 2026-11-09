# Ops review - 28 October 2026 to 31 October 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-137** (SEV2, Payments API) - About one in ten payments timed out for 40 minutes.
  Postmortem pending. Working theory: The fraud-service v2.5.0 release at 08:30 added fields to the score response and may be slowing payments down.
- **INC-138** (SEV3, accounts-service) - Customer data export requests were taking several days instead of minutes.
  Cause: The export queue query in the Accounts Service had no index on status and requested_at, and the table had grown to 40 million rows.

## Deployments
4 production deployments this period, including 1 rollback.
- Payments API v3.4.0 was rolled back to v3.3.1 on 28 October 2026.

## Notes
- Runbook review: please confirm the owner field on your team's runbooks.
- Synthetic checkout probes were extended to the mobile API.
