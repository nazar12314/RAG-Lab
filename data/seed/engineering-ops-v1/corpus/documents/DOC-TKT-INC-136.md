# INC-136: Incorrect availability badges on product pages

Severity: SEV4 | Status: Resolved | Primary service: Catalog Service
Opened: 2026-10-24 09:00 UTC (impact started 09:00 UTC)
Affected services: Catalog Service (primary)

## Description
Some product pages showed "in stock" badges for sold-out items.

## Impact
Around 90 products had wrong badges for a short time; checkout still blocked purchase of unavailable items.

## Detection
Customer report.

## Initial notes from the incident channel
Stale stock events from the inventory topic.

## Resolution note
Cause: The root cause was not determined. Stock events were verified to be correct, and the problem disappeared after the cache was flushed.
The availability badge cache in the Catalog Service was flushed.
Resolved: 2026-10-24 10:30 UTC
