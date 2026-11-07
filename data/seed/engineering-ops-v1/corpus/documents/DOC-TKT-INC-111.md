# INC-111: Duplicate order confirmation emails

Severity: SEV4 | Status: Resolved | Primary service: notification-service
Opened: 2026-06-08 19:00 UTC (impact started 14:30 UTC)
Affected services: Notification Service (primary), email-dispatcher (degraded)

## Description
Customers received the same order confirmation email two or three times.

## Impact
About 8% of confirmations were sent more than once over 21 hours.

## Detection
Customer complaints on social media.

## Initial notes from the incident channel
Mailer double-sending.

## Resolution note
Cause: The retry logic added in the Notification Service v3.1.0 release retried sends that had actually succeeded but responded slowly, and the mailer had no way to detect duplicates.
Notification Service release 3.1.1 added an idempotency key to every send so the mailer drops duplicates.
Resolved: 2026-06-09 11:30 UTC
