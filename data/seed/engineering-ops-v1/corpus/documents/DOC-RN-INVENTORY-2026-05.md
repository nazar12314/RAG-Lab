# Inventory release notes - May 2026

Production changes shipped by Inventory services in May 2026.

### Warehouse Sync v2.0.0 (release)
Deployed 2026-05-04 07:45 UTC by Ines Carvalho.
- Switched from incremental deltas to full stock snapshots every 15 minutes
- Parallel batch processing per warehouse
Status: rolled back on 4 May 2026 (to v1.9.4).

### Rollback: warehouse-sync to v1.9.4
Deployed 2026-05-04 12:30 UTC by Ines Carvalho.
- Rollback of v2.0.0 to v1.9.4

### Inventory Service v3.4.0 (release)
Deployed 2026-05-20 10:00 UTC by Jonas Lindqvist.
- Reservation expiry reduced from 30 to 15 minutes
- Stock reconciliation endpoint for warehouse sync

### Warehouse Sync v2.0.1 (release)
Deployed 2026-05-25 09:30 UTC by Ines Carvalho.
- Snapshot mode re-enabled with a version check that rejects stale snapshots

