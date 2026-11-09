# Staging load test report - spring campaign readiness

Environment: **staging**, 28 March 2026. Target: 3x the 2025 peak checkout rate.

## Results

| Step | 1x | 2x | 3x |
| --- | --- | --- | --- |
| Checkout success | 99.8% | 99.5% | 91.2% |
| p95 checkout latency | 0.9 s | 1.4 s | 4.8 s |

## Findings

1. **Connection pool exhaustion in the payments service at 3x.** The staging payment-service pods are configured with only 10 database connections each, half the production value. At 3x load the pool was exhausted and requests waited for a connection. This is a staging configuration artefact, not a production risk, but staging should mirror production pool sizes.
2. The staging database instance reached 70% CPU at 3x; production has more headroom.
3. Inventory stock checks stayed below 120 ms at all load levels with the current one-call-per-cart design.

## Recommendation

The platform is ready for the spring campaign at 2x. Raise staging pool sizes to production values before the next test.
