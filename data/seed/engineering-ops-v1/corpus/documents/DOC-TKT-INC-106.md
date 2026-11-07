# INC-106: Overselling of out-of-stock items

Severity: SEV2 | Status: Resolved | Primary service: inventory-service
Opened: 2026-05-04 10:40 UTC (impact started 08:00 UTC)
Affected services: inventory-service (primary), warehouse-sync (primary), Checkout API (downstream)

## Description
Customers were able to buy items that were already out of stock.

## Impact
640 orders were accepted for items with no stock and had to be cancelled with an apology voucher.

## Detection
Warehouse staff escalated a large number of pick failures.

## Initial notes from the incident channel
Reservation expiry bug in inventory.

## Resolution note
Warehouse Sync was rolled back to v1.9.4 (the rollback of warehouse sync worker to v1.9.4) and a reconciliation script restored correct stock levels overnight.
Full analysis in the postmortem DOC-PM-INC-106.
Resolved: 2026-05-05 09:00 UTC
