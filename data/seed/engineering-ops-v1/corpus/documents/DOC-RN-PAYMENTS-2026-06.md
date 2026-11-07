# Payments release notes - June 2026

Production changes shipped by Payments services in June 2026.

### payments-api v2.9.0 (release)
Deployed 2026-06-01 08:30 UTC by Oskar Nowak.
- Payments API now calls Fraud Scoring before authorization with a 200 ms timeout
- Transactions are declined when the fraud score is unavailable

### Payments API v2.9.1 (hotfix)
Deployed 2026-06-02 13:15 UTC by Oskar Nowak.
- Fraud call timeout raised to 800 ms
- Fail-open for low-value orders when the fraud score is unavailable

### PSP Adapter v1.6.0 (release)
Deployed 2026-06-20 07:10 UTC by Tomasz Wierzbicki.
- Support for PayNova API version 2026-06
- New metrics for authorization latency per card network

