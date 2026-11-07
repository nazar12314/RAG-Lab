# INC-124: Broken images in transactional emails

Severity: SEV4 | Status: Resolved | Primary service: Email Dispatcher
Opened: 2026-08-23 11:00 UTC (impact started 09:05 UTC)
Affected services: email worker (primary)

## Description
Logos and product images were missing from order emails.

## Impact
Emails sent over six hours displayed broken image placeholders. Content was otherwise correct.

## Detection
Internal staff noticed on their own orders.

## Initial notes from the incident channel
Asset bucket permissions.

## Resolution note
Cause: The templates in email-dispatcher release 2.3.0 referenced images with relative paths that email clients cannot resolve.
version 2.3.1 of email-dispatcher switched to absolute image URLs.
Resolved: 2026-08-23 15:10 UTC
