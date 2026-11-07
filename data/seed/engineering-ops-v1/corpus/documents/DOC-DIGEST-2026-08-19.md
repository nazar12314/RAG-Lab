# Ops review - 19 August 2026 to 1 September 2026

Prepared by Platform SRE for the fortnightly operations review.

## Incidents
- **INC-124** (SEV4, email-dispatcher) - Logos and product images were missing from order emails.
  Cause: The templates in version 2.3.0 of Email Dispatcher referenced images with relative paths that email clients cannot resolve.
- **INC-125** (SEV3, edge gateway) - Many mobile users received "Too many requests" errors.
  Cause: Rate limit policy v7 (the API Gateway config change rl-policy-v7) keyed limits by client IP. Mobile carriers place thousands of users behind shared NAT addresses, so they shared one bucket.

## Deployments
6 production deployments this period, including 1 rollback.
- edge gateway rl-policy-v7 was rolled back to rl-policy-v6 on 29 August 2026.

## Notes
- The status page template was updated with clearer wording.
- Runbook review: please confirm the owner field on your team's runbooks.
