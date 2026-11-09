# INC-121: Order notifications not sent after event bus migration

Severity: SEV2 | Status: Resolved | Primary service: notification-service
Opened: 2026-08-05 10:30 UTC (impact started 08:10 UTC)
Affected services: Notification Service (primary), Email Dispatcher (downstream)

## Description
No order confirmation or shipping emails were sent for more than three hours.

## Impact
About 15,000 notifications were not sent between 08:10 and 11:45; all were replayed by 14:00.

## Detection
Email volume anomaly detection flagged near-zero sends.

## Initial notes from the incident channel
Order Service webhook disabled too early.

## Resolution note
notification-service v4.0.1 corrected the topic name and the missed events were replayed.
Full analysis in the postmortem DOC-PM-INC-121.
Resolved: 2026-08-05 14:00 UTC
