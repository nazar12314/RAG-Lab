# Postmortem: INC-104 - Card payments failing at checkout

Date: 22 April 2026 | Authors: Payments Team | Status: Final

## Summary
Customers could not complete purchases because payment requests timed out on the final checkout step.
INC-104 was a SEV1 incident with Payments API as the primary service. Impact started at 10:12 UTC on 22 April 2026, was mitigated at 11:05 UTC and the incident was resolved at 11:40 UTC on 22 April 2026 (total 1 h 28 min).

## Customer impact
Roughly 38% of card payment attempts failed for 53 minutes. Shoppers saw "Your payment could not be processed" on the last step of checkout and many abandoned their carts.
Affected services: payments-api (primary), Checkout API (downstream)

## Timeline (UTC)
- 09:40 - Cart Service v1.12.0 deployed.
- 10:05 - payments-api release 2.8.0 rollout starts.
- 10:12 - Payment timeouts begin.
- 10:19 - CheckoutPaymentErrorRate alert fires; incident declared SEV1.
- 10:35 - Cart Service rollback considered; dashboards show cart is healthy.
- 10:48 - DB pool metrics show all 10 connections in use on every payments pod.
- 11:02 - Rollback to v2.7.3 completed.
- 11:05 - Payment success rate back to baseline.

## Root cause
The configuration refactor in version 2.8.0 of payments-api read the database pool size from a new PAYMENTS_DB_POOL_MAX variable that was never set in production, so every pod fell back to the default of 10 connections instead of 40. Under normal morning traffic the connection pool was exhausted within minutes; authorization requests queued waiting for a free connection and timed out after five seconds.
Errors started seven minutes after version 2.8.0 of Payments API reached 100% of pods.

## Ruled out
The Cart Service release deployed at 09:40 was initially suspected because of its timing, but its error rates were flat and it does not touch the payment path. It was ruled out.

## Resolution
The Payments team rolled back to v2.7.3 at 11:02 (the rollback of payments-api to v2.7.3); pool utilisation fell below 50% and payment success returned to normal by 11:05. The fixed config was re-released two weeks later.

## Action items
- [ ] Fail startup when the pool is smaller than the worker count
- [ ] Add pool saturation alert for Payments API
- [ ] Config defaults reviewed by a second engineer
