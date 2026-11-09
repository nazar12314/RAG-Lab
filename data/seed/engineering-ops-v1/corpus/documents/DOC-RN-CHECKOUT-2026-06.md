# Checkout release notes - June 2026

Production changes shipped by Checkout services in June 2026.

### co-api v5.3.0 (release)
Deployed 2026-06-01 08:00 UTC by Lena Fischer.
- Removed the direct call to Fraud Scoring; fraud checks now happen inside Payments API

### orders v4.3.0 (release)
Deployed 2026-06-23 10:00 UTC by Lena Fischer.
- Order cancellation window configurable per market

### checkout-api v5.3.2 (hotfix)
Deployed 2026-06-24 15:00 UTC by Daniel Kim.
- Fixed postcode validation for Irish Eircodes

### Cart Service v1.13.0 (release)
Deployed 2026-06-29 10:00 UTC by Daniel Kim.
- Carts of logged-in users are also written to the orders-db draft table as a fallback

