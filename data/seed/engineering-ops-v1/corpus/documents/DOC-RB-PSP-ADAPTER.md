# Runbook: PSP Adapter (provider-gateway)

Owner: Payments Team.

## What it does

The adapter translates our payment requests into PayNova API calls, including the 3-D Secure redirect and return flow.

## Alerts

- **PspAuthorizationFailureRate** - more than 5% of authorizations rejected with a 5xx from PayNova.
- **PspThreeDsReturnErrors** - spike in 404s on the 3DS return path.

## PayNova outage

1. Check the PayNova status page and the #vendor-paynova channel.
2. Compare our error codes: HTTP 503 from PayNova means the processor is down; there is nothing to roll back on our side.
3. Ask Support to suggest PayPal or gift cards. We currently have no secondary card processor.

## 3-D Secure return path

Callback URLs are registered with each acquirer at PayNova. Never change the return path without registering the new URL for every acquirer first, and keep the old path as an alias for at least a week.

## Keep-alive

The adapter closes idle client connections after 60 seconds. Clients must use a shorter idle timeout.
