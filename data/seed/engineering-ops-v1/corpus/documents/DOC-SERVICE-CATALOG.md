# Service catalog

The list of production services, their owners and the names people use for them. Keep this page up to date when a service is created, renamed or retired.

| Service | Also known as | Owner | Tier |
| --- | --- | --- | --- |
| Checkout API | co-api, checkout | Checkout Team | 1 |
| Cart Service | basket service | Checkout Team | 2 |
| Pricing Engine | pricing-service, price-calc | Checkout Team | 2 |
| Order Service | OMS, order management | Checkout Team | 1 |
| Payments API | payment-service (legacy), pay-api | Payments Team | 1 |
| Fraud Scoring Service | fraud-service, risk-scoring | Payments Team | 2 |
| Ledger Service | payments ledger | Payments Team | 2 |
| PSP Adapter | provider-gateway, psp gateway | Payments Team | 1 |
| Auth Service | identity service, IdP, login service | Identity Team | 1 |
| Accounts Service | user profile service | Identity Team | 2 |
| Inventory Service | stock service, inventory api | Inventory Team | 1 |
| Catalog Service | product catalog | Inventory Team | 2 |
| Warehouse Sync | wms sync | Inventory Team | 3 |
| Notification Service | notifier | Customer Comms Team | 2 |
| Email Dispatcher | mailer, email worker | Customer Comms Team | 3 |
| Event Bus | kafka cluster, event pipeline | Data Platform Team | 1 |
| Warehouse Loader | dw loader, nightly ETL | Data Platform Team | 3 |
| API Gateway | edge gateway, edge | Platform SRE | 1 |
| Orders DB | pg-orders, primary postgres | Platform SRE | 1 |
| Shared Redis | cache cluster, redis cache | Platform SRE | 1 |

External providers: PayNova (card processor) and MailRelay (transactional email).
