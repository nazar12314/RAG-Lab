# Ops review - 8 July 2026 to 21 July 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-116** (SEV3, event-bus) - Consumers of the event bus fell hours behind after the Kafka upgrade.
  Cause: The switch to cooperative rebalancing in the events kafka-3.7.1 upgrade combined with a too-short session timeout caused a rebalance storm; consumers kept losing partition assignments before committing offsets.
- **INC-117** (SEV4, Catalog Service) - Products added in the last two days did not appear in site search.
  Cause: catalog-service release 2.2.0 moved the search index rebuild from cron to the scheduler service, but the scheduler job was created in a disabled state, so the index was never rebuilt.
- **INC-118** (SEV2, ledger-service) - Daily ledger reconciliation found refunds recorded twice.
  Postmortem pending. Working theory: Duplicate refund events from Payments API.

## Deployments
6 production deployments this period, including 0 rollbacks.

## Notes
- Runbook review: please confirm the owner field on your team's runbooks.
- Synthetic checkout probes were extended to the mobile API.
