# INC-113: Card processor outage - payments unavailable

Severity: SEV1 | Status: Resolved | Primary service: PSP Adapter
Opened: 2026-06-20 09:08 UTC (impact started 09:05 UTC)
Affected services: psp-adapter (primary), payments-api (downstream), Checkout API (downstream)

## Description
All card payments failed for 47 minutes because the external card processor was down.

## Impact
Card payments were completely unavailable for 47 minutes; PayPal and gift cards kept working. Around 6,500 checkout attempts failed.

## Detection
PspAuthorizationFailureRate alert fired at 09:08.

## Initial notes from the incident channel
The psp-adapter v1.6.0 release this morning added support for a new PayNova API version and is the prime suspect.

## Resolution note
There was no failover processor, so the team waited for PayNova to recover at 09:52 and then monitored until 10:30.
Full analysis in the postmortem DOC-PM-INC-113.
Resolved: 2026-06-20 10:30 UTC
