# Postmortem: INC-110 - Legitimate payments declined after fraud check change

Date: 1 June 2026 | Authors: Payments Team | Status: Final

## Summary
A spike of card declines for genuine customers after fraud scoring moved into the payment flow.
INC-110 was a SEV2 incident with Payments API as the primary service. Impact started at 09:00 UTC on 1 June 2026, was mitigated at 13:15 UTC and the incident was resolved at 14:00 UTC on 2 June 2026 (total 1 d 5 h 0 min).

## Customer impact
Over 28 hours about 3% of legitimate payments were declined, concentrated at peak hours.
Affected services: payments-api (primary), fraud (degraded), Checkout API (downstream)

## Timeline (UTC)
- 08:30 - Payments API v2.9.0 deployed.
- 11:30 - Support escalates declines.
- 06-02 10:00 - Decline reason 'score unavailable' identified.
- 06-02 13:15 - Hotfix v2.9.1 deployed.

## Root cause
version 2.9.0 of payments started calling the fraud with a 200 ms timeout and declined the transaction whenever no score came back. At peak, fraud scoring p95 latency is around 350 ms, so many requests timed out and were declined without any fraud signal.
Trigger: the payment-service v2.9.0 release.

## Ruled out
The fraud model itself was unchanged; decline reasons showed "score unavailable", not high risk.

## Resolution
payments-api release 2.9.1 raised the timeout to 800 ms and made low-value orders fail open when no score is available.

## Action items
- [ ] Load test new synchronous dependencies at peak traffic
