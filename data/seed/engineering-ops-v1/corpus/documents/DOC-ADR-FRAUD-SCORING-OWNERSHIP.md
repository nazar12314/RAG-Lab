# ADR-014: Move fraud scoring into the payment flow

**Status:** Accepted. **Effective:** 1 June 2026.

## Context

Today the Checkout API calls the Fraud Scoring Service directly before payment and ignores missing scores. This means non-checkout payments (subscriptions, phone orders) are never scored, and the Payments Team cannot enforce fraud decisions.

## Decision

From 1 June 2026 the Payments API will call the Fraud Scoring Service before every authorization. Checkout will stop calling fraud scoring in the same release window (Checkout API v5.3.0, Payments API v2.9.0).

## Consequences

- Fraud scoring becomes a hard dependency of payments; its latency adds directly to authorization time.
- The timeout and fail-open policy must be agreed before launch.
- Fraud scoring keeps using account-age signals from the Accounts Service.
