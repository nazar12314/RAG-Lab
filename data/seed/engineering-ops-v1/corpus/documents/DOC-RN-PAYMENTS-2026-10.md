# Payments release notes - October 2026

Production changes shipped by Payments services in October 2026.

### PSP Adapter v1.8.0 (release)
Deployed 2026-10-01 09:00 UTC by Tomasz Wierzbicki.
- 3-D Secure callback moved to the new /v2/3ds/return path

### PSP Adapter v1.8.1 (hotfix)
Deployed 2026-10-02 14:30 UTC by Tomasz Wierzbicki.
- Legacy 3-D Secure return path kept as an alias; callback URL registered with PayNova for EU acquirer

### Payments API v3.3.1 (hotfix)
Deployed 2026-10-08 10:00 UTC by Oskar Nowak.
- Fixed rounding of partial capture amounts in JPY

### fraud-service v2.5.0 (release)
Deployed 2026-10-28 08:30 UTC by Elif Yilmaz.
- Explainability fields added to the fraud score response

### Payments API v3.4.0 (release)
Deployed 2026-10-28 09:15 UTC by Oskar Nowak.
- HTTP client library upgraded; connection keep-alive to the PSP Adapter now managed by the new client
Status: rolled back on 28 October 2026 (to v3.3.1).

### Rollback: Payments API to v3.3.1
Deployed 2026-10-28 10:05 UTC by Oskar Nowak.
- Rollback of v3.4.0 to v3.3.1

