# Postmortem: INC-131 - 3-D Secure failures for EU cards

Date: 1 October 2026 | Authors: Payments Team | Status: Final

## Summary
European customers whose bank requires 3-D Secure could not complete card payments.
INC-131 was a SEV2 incident with PSP Adapter as the primary service. Impact started at 09:10 UTC on 1 October 2026, was mitigated at 14:30 UTC and the incident was resolved at 15:00 UTC on 2 October 2026 (total 1 d 5 h 50 min).

## Customer impact
About 9% of EU card payments failed at the 3-D Secure step for 29 hours.
Affected services: PSP Adapter (primary), Payments API (downstream), Checkout API (downstream)

## Timeline (UTC)
- 09:00 - v1.8.0 deployed.
- 12:00 - EU authorization drop noticed.
- 10-02 14:30 - Hotfix deployed.

## Root cause
psp-adapter release 1.8.0 moved the 3-D Secure return URL to a new path, but the EU acquirer at PayNova still had the old callback URL registered, so customers were returned to a page that no longer existed.
Trigger: version 1.8.0 of psp-adapter.

## Resolution
version 1.8.1 of PSP Adapter restored the legacy path as an alias and registered the new callback URL with PayNova.

## Action items
- [ ] Checklist for externally registered URLs
