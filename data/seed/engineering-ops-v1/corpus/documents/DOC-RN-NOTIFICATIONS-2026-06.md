# Notifications release notes - June 2026

Production changes shipped by Notifications services in June 2026.

### notification svc v3.1.0 (release)
Deployed 2026-06-08 14:00 UTC by Ahmed Hassan.
- Automatic retries for failed sends with exponential backoff

### Notification Service v3.1.1 (hotfix)
Deployed 2026-06-09 11:30 UTC by Ahmed Hassan.
- Retries now carry an idempotency key so the mailer can drop duplicates

