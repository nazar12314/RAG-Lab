# INC-101: Stale product images on product pages

Severity: SEV4 | Status: Resolved | Primary service: Catalog Service
Opened: 2026-04-09 09:30 UTC (impact started 08:10 UTC)
Affected services: Catalog Service (primary)

## Description
Product pages showed outdated or missing images for newly updated products.

## Impact
Cosmetic only. About 1,200 products showed an old thumbnail for up to three hours; no orders were affected.

## Detection
A merchandiser reported in

## Initial notes from the incident channel
Looks like the CDN is not picking up new uploads, possibly a CDN provider issue.

## Resolution note
Cause: The new image pipeline in catalog-service release 2.1.0 set a one-week Cache-Control max-age on thumbnail URLs that do not change when the image changes, so the CDN kept serving the old file.
The team purged the CDN cache for the thumbnail path and shortened max-age to ten minutes in the service configuration.
Resolved: 2026-04-09 11:00 UTC
