# INC-103: Order confirmation emails delayed

Severity: SEV3 | Status: Resolved | Primary service: email-dispatcher
Opened: 2026-04-15 17:40 UTC (impact started 17:00 UTC)
Affected services: Email Dispatcher (primary), Notification Service (degraded)

## Description
Order confirmation and shipping emails arrived up to four hours late.

## Impact
About 22,000 transactional emails were delayed by up to four hours. No emails were lost.

## Detection
The email queue depth alert fired when the backlog exceeded 5,000 messages.

## Initial notes from the incident channel
Mailer workers may be stuck; restart them.

## Resolution note
Cause: MailRelay started returning HTTP 429 after our sending volume exceeded the account's hourly quota during a flash sale. The email-dispatcher retried with a fixed one-minute delay, which kept us above the quota.
MailRelay support raised the hourly quota at 20:10 and the backlog drained by 21:30. Restarting workers had no effect.
Resolved: 2026-04-15 21:30 UTC
