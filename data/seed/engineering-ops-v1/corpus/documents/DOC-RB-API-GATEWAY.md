# Runbook: API Gateway (edge)

Owner: Platform SRE, #sre.

## Elevated 5xx

502s from the edge usually mean an upstream is down or a TLS problem with clients. Check the per-route upstream health first. For TLS handshake failures, confirm which certificate chain is being served (`openssl s_client -connect shop.kestrel.example:443 -showcerts`). Older mobile app versions pin the previous intermediate CA.

## 429 Too Many Requests

Rate limits are defined in the policy file. Keying by client IP is unsafe for mobile traffic behind carrier NAT. Revert the policy with `edgectl policy rollback`.

## Authentication

Every authenticated route calls the Auth Service. Slow token validation shows up as gateway latency on all routes at once.
