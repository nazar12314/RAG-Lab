# Notifications release notes - August 2026

Production changes shipped by Notifications services in August 2026.

### Notification Service v4.0.0 (release)
Deployed 2026-08-05 08:00 UTC by Ahmed Hassan.
- Consumes order lifecycle events from the Event Bus instead of the Order Service webhook
- Consumer subscribes to topic configured in NOTIFY_ORDER_TOPIC (default orders.v1)

### Notification Service v4.0.1 (hotfix)
Deployed 2026-08-05 11:45 UTC by Ahmed Hassan.
- NOTIFY_ORDER_TOPIC default corrected to order-events
- Replay tool for missed order events

### email-sender v2.3.0 (release)
Deployed 2026-08-23 09:00 UTC by Sofia Marquez.
- Template assets served from the new static asset bucket

### Email Dispatcher v2.3.1 (hotfix)
Deployed 2026-08-23 15:10 UTC by Sofia Marquez.
- Absolute URLs for template images

