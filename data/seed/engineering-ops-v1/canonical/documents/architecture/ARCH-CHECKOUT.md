---
id: DOC-ARCH-CHECKOUT
title: Checkout architecture overview
doc_type: architecture
created_at: "2026-04-03T10:00:00Z"
author: Priya Raman
services: [checkout-api, cart-service, pricing-service, order-service, payments-api, fraud-service, inventory-service, auth-service]
---
# Checkout architecture overview

_Last reviewed: 3 April 2026. Owner: Checkout Team._

## Purpose

The checkout subsystem turns a cart into a paid order. It is the most revenue-critical path in Kestrel Commerce and every component on it is tier 1 or tier 2.

## Request flow

A checkout request enters through the API Gateway and is handled by the Checkout API (co-api). [[F-OWNER-checkout-api|The Checkout API is owned by the Checkout Team.]]

1. [[F-LINK-09|co-api validates the customer's session token with the Auth Service on every step.]]
2. [[F-LINK-04|It loads the basket from the Cart Service.]] [[F-LINK-20|The Cart Service itself asks the Pricing Engine for line prices]], and [[F-LINK-19|stores carts in Shared Redis]].
3. [[F-LINK-05|Checkout asks the Pricing Engine for the final price, promotions and taxes.]] [[F-LINK-21|Pricing reads product data from the Catalog Service.]]
4. [[F-LINK-07|Stock is checked and reserved through the Inventory Service.]]
5. [[F-LINK-10|Before payment, checkout calls the Fraud Scoring Service directly; a missing score does not block the order.]]
6. [[F-LINK-06|The payment is authorized by calling the Payments API (still called payment-service in some dashboards).]]
7. [[F-LINK-08|Finally the order is persisted by the Order Service]], [[F-LINK-17|which writes to the Orders DB]] [[F-LINK-34|and confirms the stock reservation with Inventory.]]

## Failure behaviour

All calls on the critical path are synchronous HTTP with a 5 second budget. If payments are slow, checkout requests pile up behind them, so the checkout dashboard is usually the first place payment problems show up. Fraud scoring is soft: when it is unavailable the order continues without a score.

## Open questions

- Should fraud scoring move into the Payments domain? A proposal is being discussed with the Payments Team.
- Saved-address prefill depends on the Accounts Service API and is planned for Q3.
