# INC-112: Profile updates failing

Severity: SEV3 | Status: Resolved | Primary service: accounts-service
Opened: 2026-06-14 07:45 UTC (impact started 03:20 UTC)
Affected services: Accounts Service (primary)

## Description
Customers could not change their address or password; the save button returned an error.

## Impact
About 2,300 failed profile update attempts over five hours. Logins and checkout were unaffected.

## Detection
Error budget burn alert for the accounts write path.

## Initial notes from the incident channel
Database disk might be full.

## Resolution note
Cause: The Accounts Service database volume ran out of disk space because audit log partitions were not being dropped after their 90-day retention.
The volume was expanded and the partition cleanup job was re-enabled.
Resolved: 2026-06-14 09:00 UTC
