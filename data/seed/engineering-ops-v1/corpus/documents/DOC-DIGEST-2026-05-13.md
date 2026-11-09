# Ops review - 13 May 2026 to 26 May 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-108** (SEV2, orders-db) - Checkout and payment requests became very slow and some failed while the orders database was overloaded.
  Postmortem pending. Working theory: Looks like the payments connection pool problem from April again.

## Deployments
4 production deployments this period, including 0 rollbacks.

## Notes
- Two new engineers joined the payments-primary rotation.
- The status page template was updated with clearer wording.
