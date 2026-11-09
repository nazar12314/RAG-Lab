# Postmortem: INC-133 - Checkout outage after new checkout release

Date: 12 October 2026 | Authors: Checkout Team | Status: Final

## Summary
Most customers could not get through checkout after the new single-page checkout launched.
INC-133 was a SEV1 incident with Checkout API as the primary service. Impact started at 08:20 UTC on 12 October 2026, was mitigated at 09:55 UTC and the incident was resolved at 10:30 UTC on 12 October 2026 (total 2 h 10 min).

## Customer impact
For 95 minutes about 70% of checkout attempts failed or timed out. Orders that did go through were correct.
Affected services: Checkout API (primary), Inventory Service (degraded), Order Service (downstream)

## Timeline (UTC)
- 08:00 - version 6.0.0 of Checkout API deployed.
- 08:24 - Checkout success alert; SEV1 declared.
- 08:45 - Inventory thread pool exhaustion observed.
- 09:10 - Rollback to v5.7.1 complete; errors drop only slightly.
- 09:50 - Inventory Service pods restarted.
- 09:55 - Checkout success rate back to normal.

## Root cause
The new flow in version 6.0.0 of checkout service performed a live stock check for every cart line on every step, increasing calls to the Inventory Service roughly twelve-fold. Inventory thread pools saturated and its responses timed out, which failed checkout.
Trigger: the checkout-api v6.0.0 release.

## Resolution
The release was rolled back to v5.7.1 at 09:10 (the rollback of checkout to v5.7.1). The rollback alone was only partially effective; inventory pods remained saturated with queued requests until they were restarted at 09:50, after which checkout success returned to normal at 09:55.

## Action items
- [ ] Batch stock checks per cart
- [ ] Load test with production-like carts
- [ ] Inventory request shedding when queues grow
