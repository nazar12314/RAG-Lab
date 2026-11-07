# Postmortem: INC-118 - Refunds double-posted in the ledger

Date: 17 July 2026 | Authors: Payments Team | Status: Final

## Summary
Daily ledger reconciliation found refunds recorded twice.
INC-118 was a SEV2 incident with Ledger Service as the primary service. Impact started at 16:10 UTC on 17 July 2026, was mitigated at 15:00 UTC and the incident was resolved at 12:00 UTC on 19 July 2026 (total 1 d 19 h 50 min).

## Customer impact
412 refunds were posted twice in the ledger, overstating refunded amounts by about 31,000 EUR. Customers were not refunded twice; the error was internal bookkeeping only.
Affected services: ledger (primary), Payments API (degraded)

## Timeline (UTC)
- 07-18 06:00 - Reconciliation mismatch.
- 07-18 15:00 - Hotfix deployed.
- 07-19 12:00 - Ledger corrected.

## Root cause
version 1.8.0 of ledger-service changed how refund postings are de-duplicated. Refund retries for refunds created before the release produced a new-style key that did not match the stored old-style key, so the retry was posted again.
Trigger: Ledger Service release 1.8.0.

## Resolution
Ledger Service v1.8.1 added a fallback to the legacy key format and Finance corrected the duplicated entries.

## Action items
- [ ] Migration plan for idempotency key format changes
