# Postmortem: INC-113 - Card processor outage - payments unavailable

Date: 20 June 2026 | Authors: Payments Team | Status: Final

## Summary
All card payments failed for 47 minutes because the external card processor was down.
INC-113 was a SEV1 incident with PSP Adapter as the primary service. Impact started at 09:05 UTC on 20 June 2026, was mitigated at 09:52 UTC and the incident was resolved at 10:30 UTC on 20 June 2026 (total 1 h 25 min).

## Customer impact
Card payments were completely unavailable for 47 minutes; PayPal and gift cards kept working. Around 6,500 checkout attempts failed.
Affected services: payment provider adapter (primary), Payments API (downstream), Checkout API (downstream)

## Timeline (UTC)
- 07:10 - the provider-gateway v1.6.0 release deployed.
- 09:05 - Authorization failures begin.
- 09:20 - PayNova status page reports an outage.
- 09:25 - Canary rollback shows no improvement.
- 09:52 - PayNova recovers.

## Root cause
PayNova had a regional outage in its EU authorization cluster and returned HTTP 503 for every authorization request. The status page confirmed the outage at 09:20.
No deployment triggered this incident.

## Ruled out
the psp-adapter v1.6.0 release was rolled back on a canary at 09:25 with no change in error rate, and PayNova confirmed the failures on their side. The release was not the cause and was kept.

## Resolution
There was no failover processor, so the team waited for PayNova to recover at 09:52 and then monitored until 10:30.

## Action items
- [ ] Evaluate a secondary card processor
- [ ] Show a clearer message suggesting alternative payment methods
