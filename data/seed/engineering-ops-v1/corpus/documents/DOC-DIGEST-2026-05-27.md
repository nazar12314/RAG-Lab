# Ops review - 27 May 2026 to 9 June 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-109** (SEV3, API Gateway) - Some mobile users saw connection errors after the TLS certificate rotation.
  Cause: The certificate rotated in the API Gateway config change edge-cert-2026-05 was issued by a new intermediate CA that old app versions did not trust because they pin the previous intermediate.
- **INC-110** (SEV2, payments backend) - A spike of card declines for genuine customers after fraud scoring moved into the payment flow.
  Postmortem pending. Working theory: The fraud model may be too aggressive.
- **INC-111** (SEV4, Notification Service) - Customers received the same order confirmation email two or three times.
  Cause: The retry logic added in Notification Service v3.1.0 retried sends that had actually succeeded but responded slowly, and the mailer had no way to detect duplicates.

## Deployments
7 production deployments this period, including 0 rollbacks.

## Notes
- Alert noise review: 14 alerts were tuned or deleted.
- Game day planned for the next period; volunteers welcome.
