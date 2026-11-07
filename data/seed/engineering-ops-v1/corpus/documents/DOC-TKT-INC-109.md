# INC-109: Elevated 502 errors on older Android app versions

Severity: SEV3 | Status: Resolved | Primary service: API Gateway
Opened: 2026-05-27 07:20 UTC (impact started 06:05 UTC)
Affected services: api-gateway (primary)

## Description
Some mobile users saw connection errors after the TLS certificate rotation.

## Impact
About 4% of mobile sessions, all on app versions older than 5.0, failed to connect for three hours.

## Detection
Mobile crash analytics showed TLS handshake failures.

## Initial notes from the incident channel
A CDN routing issue.

## Resolution note
Cause: The certificate rotated in the API Gateway config change edge-cert-2026-05 was issued by a new intermediate CA that old app versions did not trust because they pin the previous intermediate.
The edge was configured to serve the cross-signed chain, which older clients accept.
Resolved: 2026-05-27 09:00 UTC
