# Authentication security review - H1 2026

## Scope

Token issuance and validation in the Auth Service, session storage, and edge token checks.

## Findings

1. **Manual signing key rotation (medium).** The JWT signing key is rotated by hand every quarter using a calendar reminder. There is no alert before expiry. Recommendation: automate rotation and alert 14 days before expiry. Status: accepted, not yet scheduled.
2. **JWKS caching (low).** Validators cache the key set indefinitely. A planned change will refresh it more often.
3. **Password reset rate limiting (resolved).** Added in v6.1.4.

## Out of scope

Third-party identity providers and the mobile app's certificate pinning.
