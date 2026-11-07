# Shared Infrastructure release notes - August 2026

Production changes shipped by Shared Infrastructure services in August 2026.

### Config: edge gateway rl-policy-v7
Deployed 2026-08-29 13:00 UTC by Hannah Becker.
- Rate limit keyed by client IP instead of API key
Status: rolled back on 29 August 2026 (to rl-policy-v6).

### Rollback: edge gateway to rl-policy-v6
Deployed 2026-08-29 14:05 UTC by Hannah Becker.
- Reverted rate limit policy to v6

