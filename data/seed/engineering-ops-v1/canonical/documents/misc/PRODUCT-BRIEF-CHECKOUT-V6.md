---
id: DOC-PRODUCT-BRIEF-CHECKOUT-V6
title: "Product brief: single-page checkout (Checkout v6)"
doc_type: product_brief
created_at: "2026-08-25T10:00:00Z"
author: Priya Raman
services: [checkout-api, inventory-service]
---
# Product brief: single-page checkout (Checkout v6)

## Goal

Increase mobile conversion by 4% by replacing the four-step checkout with a single page.

## Key features

- All steps (address, delivery, payment, review) on one page.
- **Always-accurate stock:** every cart line is re-checked against live stock whenever the customer changes anything on the page, so customers never pay for an item that just sold out.
- Express payment buttons at the top.

## Launch plan

Release as Checkout API 6.0 in October, behind no flag, because the old and new flows cannot share session state. Marketing campaign starts the same week.

## Success metrics

Conversion, time to complete checkout, and stock-related order cancellations.
