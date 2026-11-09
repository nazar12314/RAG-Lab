---
id: DOC-SERVICE-CATALOG
title: Service catalog
doc_type: reference
created_at: "2026-04-01T08:00:00Z"
author: Hannah Becker
services: []
---
# Service catalog

The list of production services, their owners and the names people use for them. Keep this page up to date when a service is created, renamed or retired.

| Service | Also known as | Owner | Tier |
| --- | --- | --- | --- |
| [[F-OWNER-checkout-api|Checkout API | co-api, checkout | Checkout Team]] | 1 |
| [[F-OWNER-cart-service|Cart Service | basket service | Checkout Team]] | 2 |
| [[F-OWNER-pricing-service|Pricing Engine | pricing-service, price-calc | Checkout Team]] | 2 |
| [[F-OWNER-order-service|Order Service | OMS, order management | Checkout Team]] | 1 |
| [[F-OWNER-payments-api|Payments API | payment-service (legacy), pay-api | Payments Team]] | 1 |
| [[F-OWNER-fraud-service|Fraud Scoring Service | fraud-service, risk-scoring | Payments Team]] | 2 |
| [[F-OWNER-ledger-service|Ledger Service | payments ledger | Payments Team]] | 2 |
| [[F-OWNER-psp-adapter|PSP Adapter | provider-gateway, psp gateway | Payments Team]] | 1 |
| [[F-OWNER-auth-service|Auth Service | identity service, IdP, login service | Identity Team]] | 1 |
| [[F-OWNER-accounts-service|Accounts Service | user profile service | Identity Team]] | 2 |
| [[F-OWNER-inventory-service|Inventory Service | stock service, inventory api | Inventory Team]] | 1 |
| [[F-OWNER-catalog-service|Catalog Service | product catalog | Inventory Team]] | 2 |
| [[F-OWNER-warehouse-sync|Warehouse Sync | wms sync | Inventory Team]] | 3 |
| [[F-OWNER-notification-service|Notification Service | notifier | Customer Comms Team]] | 2 |
| [[F-OWNER-email-dispatcher|Email Dispatcher | mailer, email worker | Customer Comms Team]] | 3 |
| [[F-OWNER-event-bus|Event Bus | kafka cluster, event pipeline | Data Platform Team]] | 1 |
| [[F-OWNER-warehouse-loader|Warehouse Loader | dw loader, nightly ETL | Data Platform Team]] | 3 |
| [[F-OWNER-api-gateway|API Gateway | edge gateway, edge | Platform SRE]] | 1 |
| [[F-OWNER-orders-db|Orders DB | pg-orders, primary postgres | Platform SRE]] | 1 |
| [[F-OWNER-shared-redis|Shared Redis | cache cluster, redis cache | Platform SRE]] | 1 |

External providers: PayNova (card processor) and MailRelay (transactional email).
