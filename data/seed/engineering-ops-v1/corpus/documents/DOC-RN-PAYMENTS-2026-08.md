# Payments release notes - August 2026

Production changes shipped by Payments services in August 2026.

### psp-adapter v1.7.0 (release)
Deployed 2026-08-03 10:00 UTC by Tomasz Wierzbicki.
- Network token support for Visa and Mastercard

### Payments API v3.1.0 (release)
Deployed 2026-08-17 08:10 UTC by Oskar Nowak.
- New settlement reconciliation endpoint used by Finance dashboards
- Refund listing supports filtering by settlement batch

### payments v3.1.1 (hotfix)
Deployed 2026-08-17 12:40 UTC by Oskar Nowak.
- Index on payments(settlement_batch_id, created_at)
- Reconciliation endpoint kept behind the recon_v2 feature flag

