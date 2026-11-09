# Checkout release notes - April 2026

Production changes shipped by Checkout services in April 2026.

### Checkout API v5.2.0 (release)
Deployed 2026-04-01 09:15 UTC by Lena Fischer.
- Gift-card balance shown on the review step
- Upgraded Spring Boot to 3.4.2

### Order Service v4.1.0 (release)
Deployed 2026-04-14 13:20 UTC by Lena Fischer.
- Added partial-shipment support to the order state machine

### Cart Service v1.12.0 (release)
Deployed 2026-04-22 09:40 UTC by Daniel Kim.
- Cart TTL extended from 7 to 14 days
- Added cart merge on login

### Order Service v4.2.0 (release)
Deployed 2026-04-27 08:30 UTC by Lena Fischer.
- Database migration renames orders.shipping_addr to orders.shipping_address
- Order history API returns full address objects

