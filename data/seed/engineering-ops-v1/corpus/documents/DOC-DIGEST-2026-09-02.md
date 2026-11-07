# Ops review - 2 September 2026 to 15 September 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-126** (SEV2, checkout-api) - Checkout became very slow early in the morning while Redis was being patched.
  Postmortem pending. Working theory: Checkout API garbage collection pauses.
- **INC-127** (SEV3, Fraud Scoring Service) - Fraud declines tripled after the new fraud model went live.
  Cause: risk-scoring release 2.4.0 combined a new model with a lower decline threshold (0.85 instead of 0.92); the combination flagged many legitimate first-time customers.
- **INC-128** (SEV4, Warehouse Sync) - Stock levels from the partner warehouse stopped updating overnight.
  Cause: The partner WMS rotated its API credentials at midnight as announced in an email that went to an unmonitored mailbox, so every sync request was rejected with 401.

## Deployments
6 production deployments this period, including 1 rollback.
- Fraud Scoring Service v2.4.0 was rolled back to v2.3.2 on 9 September 2026.

## Notes
- Two new engineers joined the payments-primary rotation.
- The status page template was updated with clearer wording.
