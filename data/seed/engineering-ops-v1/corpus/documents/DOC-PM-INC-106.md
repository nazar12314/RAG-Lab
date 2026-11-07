# Postmortem: INC-106 - Overselling of out-of-stock items

Date: 4 May 2026 | Authors: Inventory Team | Status: Final

## Summary
Customers were able to buy items that were already out of stock.
INC-106 was a SEV2 incident with Inventory Service as the primary service. Impact started at 08:00 UTC on 4 May 2026, was mitigated at 12:30 UTC and the incident was resolved at 09:00 UTC on 5 May 2026 (total 1 d 1 h 0 min).

## Customer impact
640 orders were accepted for items with no stock and had to be cancelled with an apology voucher.
Affected services: Inventory Service (primary), warehouse-sync (primary), checkout-api (downstream)

## Timeline (UTC)
- 07:45 - wms sync v2.0.0 deployed.
- 10:40 - Pick failures escalated.
- 12:30 - Rollback to v1.9.4.
- 05-05 09:00 - Reconciliation finished.

## Root cause
Warehouse Sync release 2.0.0 replaced incremental stock deltas with full snapshots processed in parallel. Snapshots from different warehouses overwrote each other's newer counts with older values, so sold-out items reappeared as in stock.
Trigger: the warehouse-sync v2.0.0 release.

## Resolution
Warehouse Sync was rolled back to v1.9.4 (the rollback of Warehouse Sync to v1.9.4) and a reconciliation script restored correct stock levels overnight.

## Action items
- [ ] Reject snapshots older than current stock version
