---
id: DOC-RB-PAYMENTS-API
title: "Runbook: Payments API"
doc_type: runbook
created_at: "2026-05-08T10:00:00Z"
author: Oskar Nowak
services: [payments-api, orders-db, psp-adapter, fraud-service]
---
# Runbook: Payments API (payment-service)

Owner: Payments Team, #team-payments. Pager rotation: payments-primary.

## Alerts

- **PaymentAuthLatency** - p95 authorization latency above 1.5 s for 5 minutes.
- **PaymentsDbPoolSaturation** - more than 90% of database connections in use on any pod. Added after INC-104.
- **CheckoutPaymentErrorRate** - owned by Checkout but usually means a payments problem.

## Connection pool exhaustion

Symptoms: authorization requests time out after about 5 seconds, logs show `QueuePool limit reached` or `timeout waiting for connection`, and the pool gauge sits at its maximum.

1. Check `payments_db_pool_in_use` against `payments_db_pool_max` per pod. [[F-LINK-14|Every pod holds its own pool against pg-orders.]] The expected maximum is 40.
2. If the maximum is lower than 40, the pool size configuration is wrong - check `PAYMENTS_DB_POOL_MAX` and roll back the last release if it changed config.
3. If the pool is full but the maximum is correct, the database itself is probably slow. Look at the Orders DB runbook for saturation and long-running queries before scaling pay-api: adding pods adds connections and can make database saturation worse.

## PSP timeouts

[[F-LINK-12|Authorizations are forwarded to the PSP Adapter.]] If only the PSP call is slow, check the PSP Adapter dashboard and the PayNova status page. Client-side keep-alive and idle timeouts must be shorter than the adapter's (60 s).

## Fraud scoring

Fraud scoring has been called by pay-api since June. A slow fraud service shows up as "score unavailable" declines, not as timeouts.

## Rollback

`deployctl rollback payments-api --to <previous-version>`. A rollback takes about 3 minutes for all pods.
