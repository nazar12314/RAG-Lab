# Runbook: Auth Service (identity service)

Owner: Identity Team, #team-identity.

## Alerts

- **AuthSessionMissRateHigh** - more than 2% of session lookups miss.
- **AuthErrorRate** - more than 1% failed logins with 5xx.
- **TokenValidationLatency** - p95 above 300 ms.

## Users being logged out

Sessions live in the Shared Redis session shards. If users are randomly logged out:

1. Check `evicted_keys` on the session shards. Any evictions mean Redis is out of memory and is dropping sessions.
2. Check for a recent failover of a session shard.
3. Do not flush the session shards - that logs out everyone.

## Token validation slow

Token validation must use the cached JWKS key set. If latency rises after a release, roll back first.

## Signing key expiry

The signing key is rotated quarterly by hand. If all tokens suddenly fail validation at a fixed time (often midnight UTC), check the key expiry: `authctl keys list`. Emergency rotation: `authctl keys rotate --emergency`.
