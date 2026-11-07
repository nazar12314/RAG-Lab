# Postmortem: INC-115 - Checkout errors for customers with saved addresses

Date: 1 July 2026 | Authors: Checkout Team | Status: Final

## Summary
Returning customers with a saved address got a server error on the shipping step.
INC-115 was a SEV2 incident with Checkout API as the primary service. Impact started at 09:20 UTC on 1 July 2026, was mitigated at 08:20 UTC and the incident was resolved at 08:30 UTC on 2 July 2026 (total 23 h 10 min).

## Customer impact
About 11% of checkout sessions hit an HTTP 500 on the shipping step for almost a day.
Affected services: co-api (primary)

## Timeline (UTC)
- 09:00 - the checkout-api v5.4.0 release deployed.
- 09:35 - Alert.
- 07-02 08:20 - Rolled back.

## Root cause
Checkout API release 5.4.0 pre-filled saved addresses but did not handle addresses with an empty second address line, throwing a NullPointerException.
Trigger: the checkout-api v5.4.0 release.

## Resolution
The release was rolled back to v5.3.2 the next morning (the rollback of checkout-api to v5.3.2) after a forward fix failed review.

## Action items
- [ ] Contract tests against real Accounts Service payloads
