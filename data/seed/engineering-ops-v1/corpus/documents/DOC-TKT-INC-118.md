# INC-118: Refunds double-posted in the ledger

Severity: SEV2 | Status: Resolved | Primary service: finance ledger
Opened: 2026-07-18 06:00 UTC (impact started 16:10 UTC)
Affected services: ledger-service (primary), payments (degraded)

## Description
Daily ledger reconciliation found refunds recorded twice.

## Impact
412 refunds were posted twice in the ledger, overstating refunded amounts by about 31,000 EUR. Customers were not refunded twice; the error was internal bookkeeping only.

## Detection
Nightly reconciliation job reported a mismatch between the PSP settlement file and the ledger.

## Initial notes from the incident channel
Duplicate refund events from Payments API.

## Resolution note
version 1.8.1 of ledger-service added a fallback to the legacy key format and Finance corrected the duplicated entries.
Full analysis in the postmortem DOC-PM-INC-118.
Resolved: 2026-07-19 12:00 UTC
