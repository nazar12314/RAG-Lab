# Postmortem: INC-121 - Order notifications not sent after event bus migration

Date: 5 August 2026 | Authors: Customer Comms Team | Status: Final

## Summary
No order confirmation or shipping emails were sent for more than three hours.
INC-121 was a SEV2 incident with Notification Service as the primary service. Impact started at 08:10 UTC on 5 August 2026, was mitigated at 11:45 UTC and the incident was resolved at 14:00 UTC on 5 August 2026 (total 5 h 50 min).

## Customer impact
About 15,000 notifications were not sent between 08:10 and 11:45; all were replayed by 14:00.
Affected services: Notification Service (primary), mailer (downstream)

## Timeline (UTC)
- 08:00 - the notification-service v4.0.0 release deployed; webhook disabled.
- 10:30 - Anomaly flagged.
- 11:45 - Hotfix deployed.
- 14:00 - Replay complete.

## Root cause
the Notification Service v4.0.0 release switched the notification-service from the Order Service webhook to the event-bus, but the consumer subscribed to the default topic orders.v1, which no longer receives events. The production topic is order-events.
Trigger: notification svc v4.0.0.

## Resolution
Notification Service release 4.0.1 corrected the topic name and the missed events were replayed.

## Action items
- [ ] Staging check that consumers receive at least one event after deploy
