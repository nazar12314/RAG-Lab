# Inventory release notes - August 2026

Production changes shipped by Inventory services in August 2026.

### Inventory Service v3.6.0 (release)
Deployed 2026-08-05 07:00 UTC by Jonas Lindqvist.
- Publishes stock-changed events to the Event Bus topic stock-events

### Inventory Service v3.6.1 (hotfix)
Deployed 2026-08-12 10:30 UTC by Jonas Lindqvist.
- Stock events carry a deterministic event id for consumer-side de-duplication
- Producer retries made idempotent

