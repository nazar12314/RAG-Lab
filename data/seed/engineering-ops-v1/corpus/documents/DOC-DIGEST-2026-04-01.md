# Ops review - 1 April 2026 to 14 April 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-101** (SEV4, Catalog Service) - Product pages showed outdated or missing images for newly updated products.
  Cause: The new image pipeline in version 2.1.0 of Catalog Service set a one-week Cache-Control max-age on thumbnail URLs that do not change when the image changes, so the CDN kept serving the old file.
- **INC-102** (SEV2, auth-service) - Customers were randomly signed out, including in the middle of checkout, and some could not log back in.
  Postmortem pending. Working theory: Suspect the auth-service v6.0.0 session key prefix change from earlier this week.

## Deployments
6 production deployments this period, including 0 rollbacks.

## Notes
- On-call handovers happened on time for all rotations.
- Reminder: the Friday afternoon change freeze applies to all tier 1 services.
