# Checkout release notes - October 2026

Production changes shipped by Checkout services in October 2026.

### checkout-api v6.0.0 (release)
Deployed 2026-10-12 08:00 UTC by Lena Fischer.
- New single-page checkout flow
- Live stock check for every cart line on each step
Status: rolled back on 12 October 2026 (to v5.7.1).

### Rollback: Checkout API to v5.7.1
Deployed 2026-10-12 09:10 UTC by Lena Fischer.
- Rollback of v6.0.0 to v5.7.1

### Pricing Engine v2.7.0 (release)
Deployed 2026-10-15 10:00 UTC by Yusuf Demir.
- Multi-currency price lists
- Rounding moved from cart-level to line-level

### Pricing Engine v2.7.1 (hotfix)
Deployed 2026-10-16 12:00 UTC by Yusuf Demir.
- Line-level rounding uses banker's rounding to match the Cart Service

