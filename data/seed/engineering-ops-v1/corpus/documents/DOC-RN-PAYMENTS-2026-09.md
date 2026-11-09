# Payments release notes - September 2026

Production changes shipped by Payments services in September 2026.

### Fraud Scoring Service v2.4.0 (release)
Deployed 2026-09-09 09:00 UTC by Elif Yilmaz.
- Model v24 with device fingerprint features
- Decline threshold lowered from 0.92 to 0.85
Status: rolled back on 9 September 2026 (to v2.3.2).

### Rollback: Fraud Scoring Service to v2.3.2
Deployed 2026-09-09 16:30 UTC by Elif Yilmaz.
- Rollback of v2.4.0 to v2.3.2

### payments-api v3.2.0 (release)
Deployed 2026-09-10 10:00 UTC by Oskar Nowak.
- Partial captures for split shipments

### Fraud Scoring Service v2.4.1 (release)
Deployed 2026-09-23 10:00 UTC by Elif Yilmaz.
- Model v24 re-released with the 0.92 decline threshold

### pay-api v3.3.0 (release)
Deployed 2026-09-29 10:00 UTC by Oskar Nowak.
- Apple Pay merchant validation moved server-side

