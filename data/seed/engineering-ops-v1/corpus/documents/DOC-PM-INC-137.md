# Postmortem: INC-137 - Intermittent payment timeouts after HTTP client upgrade

Date: 28 October 2026 | Authors: Payments Team | Status: Final

## Summary
About one in ten payments timed out for 40 minutes.
INC-137 was a SEV2 incident with Payments API as the primary service. Impact started at 09:25 UTC on 28 October 2026, was mitigated at 10:05 UTC and the incident was resolved at 10:30 UTC on 28 October 2026 (total 1 h 5 min).

## Customer impact
11% of payment authorizations timed out between 09:25 and 10:05; customers could retry, and about half of them succeeded on retry.
Affected services: Payments API (primary), PSP Adapter (degraded), checkout service (downstream)

## Timeline (UTC)
- 08:30 - the fraud v2.5.0 release deployed.
- 09:15 - the payments-api v3.4.0 release deployed.
- 09:31 - Latency alert.
- 09:50 - Timeouts isolated to the PSP Adapter call.
- 10:05 - Rollback complete.

## Root cause
The HTTP client upgrade in the Payments API v3.4.0 release changed connection reuse so that idle keep-alive connections to the PSP Adapter were reused after the adapter had already closed them. Requests sent on those dead sockets hung until the 10 second client timeout.
Trigger: version 3.4.0 of Payments API.

## Ruled out
version 2.5.0 of Fraud Scoring Service was suspected because it shipped 45 minutes earlier, but fraud scoring latency was unchanged and timeouts were only on the PSP Adapter call. It was ruled out.

## Resolution
Payments API was rolled back to v3.3.1 at 10:05 (the rollback of Payments API to v3.3.1) and timeouts stopped immediately.

## Action items
- [ ] Set idle connection timeout below the adapter's keep-alive timeout
- [ ] Canary analysis for client library upgrades
