# INC-117: New products missing from search

Severity: SEV4 | Status: Resolved | Primary service: Catalog Service
Opened: 2026-07-17 10:00 UTC (impact started 14:00 UTC)
Affected services: Catalog Service (primary)

## Description
Products added in the last two days did not appear in site search.

## Impact
About 300 new products were not searchable for two days.

## Detection
Merchandising team report.

## Initial notes from the incident channel
Event bus lag again - catalog may not be receiving product events.

## Resolution note
Cause: Catalog Service v2.2.0 moved the search index rebuild from cron to the scheduler service, but the scheduler job was created in a disabled state, so the index was never rebuilt.
The scheduler job was enabled and a manual reindex was run.
Resolved: 2026-07-17 12:00 UTC
