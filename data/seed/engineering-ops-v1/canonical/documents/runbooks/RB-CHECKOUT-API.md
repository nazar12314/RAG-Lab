---
id: DOC-RB-CHECKOUT-API
title: "Runbook: Checkout API"
doc_type: runbook
created_at: "2026-07-05T10:00:00Z"
author: Daniel Kim
services: [checkout-api, payments-api, inventory-service, pricing-service, cart-service]
---
# Runbook: Checkout API

Owner: Checkout Team, #team-checkout.

## Alerts

- **CheckoutSuccessRate** - fewer than 92% of started checkouts complete within 10 minutes.
- **Checkout5xxRate** - more than 1% HTTP 5xx responses.
- **CheckoutLatencyHigh** - p95 of any step above 2 s.

## First five minutes

Checkout fails whenever one of its synchronous dependencies fails, so start by finding which downstream call is slow:

| Downstream | Dashboard panel |
| --- | --- |
| Payments API | "payment authorize" span |
| Inventory Service | "stock check / reserve" span |
| Pricing Engine | "price quote" span |
| Cart Service | "load cart" span |

[[F-LINK-06|A failing payment step almost always means Payments API is unhealthy]]; switch to the Payments runbook. [[F-LINK-07|Stock check timeouts point to the Inventory Service]] - check its thread pool saturation and request queue.

## Our own releases

If errors started within 30 minutes of a co-api release, roll back first and investigate later: `deployctl rollback checkout-api --to <previous-version>`. Remember that a rollback does not drain queues in downstream services; a dependency may need a restart.

## Customer-facing messaging

If checkout success is below 80% for more than 10 minutes, ask Support to post the status banner.
