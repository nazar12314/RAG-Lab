# INC-131: 3-D Secure failures for EU cards

Severity: SEV2 | Status: Resolved | Primary service: PSP Adapter
Opened: 2026-10-01 12:00 UTC (impact started 09:10 UTC)
Affected services: PSP Adapter (primary), Payments API (downstream), checkout-api (downstream)

## Description
European customers whose bank requires 3-D Secure could not complete card payments.

## Impact
About 9% of EU card payments failed at the 3-D Secure step for 29 hours.

## Detection
Payments team noticed a drop in EU authorization rate.

## Initial notes from the incident channel
A bank-side 3DS issue.

## Resolution note
the provider-gateway v1.8.1 release restored the legacy path as an alias and registered the new callback URL with PayNova.
Full analysis in the postmortem DOC-PM-INC-131.
Resolved: 2026-10-02 15:00 UTC
