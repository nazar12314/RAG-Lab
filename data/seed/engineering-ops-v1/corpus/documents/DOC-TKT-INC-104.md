# INC-104: Card payments failing at checkout

Severity: SEV1 | Status: Resolved | Primary service: Payments API
Opened: 2026-04-22 10:19 UTC (impact started 10:12 UTC)
Affected services: Payments API (primary), checkout-api (downstream)

## Description
Customers could not complete purchases because payment requests timed out on the final checkout step.

## Impact
Roughly 38% of card payment attempts failed for 53 minutes. Shoppers saw "Your payment could not be processed" on the last step of checkout and many abandoned their carts.

## Detection
The CheckoutPaymentErrorRate alert fired at 10:19 and support reported a surge of customers unable to pay.

## Initial notes from the incident channel
The cart-service v1.12.0 release (cart merge on login) went out at 09:40, shortly before errors began, and is the main suspect.

## Resolution note
The Payments team rolled back to v2.7.3 at 11:02 (the rollback of payments backend to v2.7.3); pool utilisation fell below 50% and payment success returned to normal by 11:05. The fixed config was re-released two weeks later.
Full analysis in the postmortem DOC-PM-INC-104.
Resolved: 2026-04-22 11:40 UTC
