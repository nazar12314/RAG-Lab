# Payments release notes - April 2026

Production changes shipped by Payments services in April 2026.

### pay-api v2.7.3 (hotfix)
Deployed 2026-04-16 10:00 UTC by Oskar Nowak.
- Fixed currency code validation for refunds in CHF

### payments-api v2.8.0 (release)
Deployed 2026-04-22 10:05 UTC by Oskar Nowak.
- Refactored database settings into a typed config module; pool size is now read from PAYMENTS_DB_POOL_MAX (default 10)
- Added structured logging for authorization requests
Status: rolled back on 22 April 2026 (to v2.7.3).

### Rollback: payments-api to v2.7.3
Deployed 2026-04-22 11:02 UTC by Oskar Nowak.
- Rollback of v2.8.0 to v2.7.3

