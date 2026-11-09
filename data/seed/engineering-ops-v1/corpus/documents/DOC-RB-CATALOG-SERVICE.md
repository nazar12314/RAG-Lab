# Runbook: Catalog Service

Owner: Inventory Team.

## Stale images or product data

Check the Cache-Control headers returned for the asset. Purge the CDN path with `cdnctl purge /img/thumbs/*`. Thumbnail URLs are not content-addressed, so long max-age values cause stale images.

## Cache miss storm

The catalog read-through cache lives in Shared Redis. After a Redis restart the cache is empty and every request hits the catalog database. Enable request coalescing (`CATALOG_COALESCE=true`) and warm the cache from the latest snapshot: `catalogctl cache warm --from-snapshot latest`.

## Search index

New products appear in search only after the index rebuild job runs. Check the job status in the scheduler and the `search_index_age_seconds` metric.

## Availability badges

Badges are cached separately for 10 minutes. If badges disagree with stock, flush the badge cache.
