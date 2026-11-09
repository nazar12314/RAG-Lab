# Payments release notes - July 2026

Production changes shipped by Payments services in July 2026.

### payments-api v3.0.0 (release)
Deployed 2026-07-15 10:00 UTC by Oskar Nowak.
- New refunds API v2
- Dropped the deprecated payment-service hostname alias

### Ledger Service v1.8.0 (release)
Deployed 2026-07-17 16:00 UTC by Marta Kowalczyk.
- Idempotency key for refund postings now derived from refund id instead of payment id + amount

### ledger-service v1.8.1 (hotfix)
Deployed 2026-07-18 15:00 UTC by Marta Kowalczyk.
- Idempotency key falls back to the legacy format for refunds created before v1.8.0

### Fraud Scoring Service v2.3.2 (release)
Deployed 2026-07-28 11:00 UTC by Elif Yilmaz.
- Model v23 retrained on Q2 data

