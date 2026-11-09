# INC-138: Privacy data exports taking days

Severity: SEV3 | Status: Monitoring | Primary service: Accounts Service
Opened: 2026-10-30 08:00 UTC (impact started 08:00 UTC)
Affected services: accounts-service (primary)

## Description
Customer data export requests were taking several days instead of minutes.

## Impact
About 140 privacy export requests were delayed; the legal response deadline was not breached.

## Detection
Privacy team report.

## Initial notes from the incident channel
Export worker crashed.

## Resolution note
Cause: The export queue query in the accounts had no index on status and requested_at, and the table had grown to 40 million rows.
An index was added in Accounts Service release 1.5.1; the team is monitoring the backlog before closing the incident.
Mitigated: 2026-10-31 11:00 UTC; still being monitored.
